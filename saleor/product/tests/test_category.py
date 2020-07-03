from unittest.mock import patch

from ..models import Category
from ..utils import collect_categories_tree_products, delete_categories


def test_collect_categories_tree_products(categories_tree):
    parent = categories_tree
    child = parent.children.first()
    products = parent.products.all() | child.products.all()

    result = collect_categories_tree_products(parent)

    assert len(result) == len(products)
    assert set(result.values_list("pk", flat=True)) == set(
        products.values_list("pk", flat=True)
    )


@patch("saleor.product.utils.update_products_minimal_variant_prices_task")
def test_delete_categories(
    mock_update_products_minimal_variant_prices_task,
    categories_tree_with_published_products,
):
    parent = categories_tree_with_published_products
    child = parent.children.first()
    product_list = [child.products.first(), parent.products.first()]

    delete_categories([parent.pk])

    assert not Category.objects.filter(
        id__in=[category.id for category in [parent, child]]
    ).exists()

    calls = mock_update_products_minimal_variant_prices_task.mock_calls
    assert len(calls) == 1
    call_kwargs = calls[0].kwargs
    assert set(call_kwargs["product_ids"]) == {p.pk for p in product_list}

    for product in product_list:
        product.refresh_from_db()
        assert not product.category
        assert not product.is_published
        assert not product.publication_date
