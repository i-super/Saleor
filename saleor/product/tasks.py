import logging
from typing import Iterable, List, Optional

from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from ..attribute.models import Attribute
from ..celeryconf import app
from ..core.exceptions import PreorderAllocationError
from ..discount.models import Sale
from ..warehouse.management import deactivate_preorder_for_variant
from .models import Product, ProductType, ProductVariant
from .search import PRODUCTS_BATCH_SIZE, update_products_search_vector
from .utils.variant_prices import (
    update_products_discounted_price,
    update_products_discounted_prices,
    update_products_discounted_prices_of_catalogues,
    update_products_discounted_prices_of_sale,
)
from .utils.variants import generate_and_set_variant_name

logger = logging.getLogger(__name__)
task_logger = get_task_logger(__name__)

VARIANTS_UPDATE_BATCH = 500


def _variants_in_batches(variants_qs):
    """Slice a variants queryset into batches."""
    start_pk = 0

    while True:
        variants = list(
            variants_qs.order_by("pk").filter(pk__gt=start_pk)[:VARIANTS_UPDATE_BATCH]
        )
        if not variants:
            break
        yield variants
        start_pk = variants[-1].pk


def _update_variants_names(instance: ProductType, saved_attributes: Iterable):
    """Product variant names are created from names of assigned attributes.

    After change in attribute value name, for all product variants using this
    attributes we need to update the names.
    """
    initial_attributes = set(instance.variant_attributes.all())
    attributes_changed = initial_attributes.intersection(saved_attributes)
    if not attributes_changed:
        return

    variants = ProductVariant.objects.filter(
        product__in=instance.products.all(),
        product__product_type__variant_attributes__in=attributes_changed,
    )

    for variants_batch in _variants_in_batches(variants):
        variants_to_update = [
            generate_and_set_variant_name(variant, variant.sku, save=False)
            for variant in variants_batch
        ]
        ProductVariant.objects.bulk_update(variants_to_update, ["name", "updated_at"])


@app.task
def update_variants_names(product_type_pk: int, saved_attributes_ids: List[int]):
    try:
        instance = ProductType.objects.get(pk=product_type_pk)
    except ObjectDoesNotExist:
        logging.warning(f"Cannot find product type with id: {product_type_pk}.")
        return
    saved_attributes = Attribute.objects.filter(pk__in=saved_attributes_ids)
    _update_variants_names(instance, saved_attributes)


@app.task
def update_product_discounted_price_task(product_pk: int):
    try:
        product = Product.objects.get(pk=product_pk)
    except ObjectDoesNotExist:
        logging.warning(f"Cannot find product with id: {product_pk}.")
        return
    update_products_discounted_price([product])


@app.task
def update_products_discounted_prices_of_catalogues_task(
    product_ids: Optional[List[int]] = None,
    category_ids: Optional[List[int]] = None,
    collection_ids: Optional[List[int]] = None,
    variant_ids: Optional[List[int]] = None,
):
    update_products_discounted_prices_of_catalogues(
        product_ids, category_ids, collection_ids, variant_ids
    )


@app.task
def update_products_discounted_prices_of_sale_task(discount_pk: int):
    try:
        discount = Sale.objects.get(pk=discount_pk)
    except ObjectDoesNotExist:
        logging.warning(f"Cannot find discount with id: {discount_pk}.")
        return
    update_products_discounted_prices_of_sale(discount)


@app.task
def update_products_discounted_prices_task(product_ids: List[int]):
    products = Product.objects.filter(pk__in=product_ids)
    update_products_discounted_prices(products)


@app.task
def deactivate_preorder_for_variants_task():
    variants_to_clean = _get_preorder_variants_to_clean()

    for variant in variants_to_clean:
        try:
            deactivate_preorder_for_variant(variant)
        except PreorderAllocationError as e:
            task_logger.warning(str(e))


def _get_preorder_variants_to_clean():
    return ProductVariant.objects.filter(
        is_preorder=True, preorder_end_date__lt=timezone.now()
    )


@app.task(
    queue=settings.UPDATE_SEARCH_VECTOR_INDEX_QUEUE_NAME,
    expires=settings.BEAT_UPDATE_SEARCH_EXPIRE_AFTER_SEC,
)
def update_products_search_vector_task():
    products = Product.objects.filter(search_index_dirty=True).order_by()[
        :PRODUCTS_BATCH_SIZE
    ]
    update_products_search_vector(products, use_batches=False)
