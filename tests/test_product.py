import datetime
import os
import re
from decimal import Decimal
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup, Tag
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from freezegun import freeze_time
from prices import Money, MoneyRange, TaxedMoney

from saleor.account import events as account_events
from saleor.checkout import utils
from saleor.checkout.models import Checkout
from saleor.checkout.utils import add_variant_to_checkout
from saleor.menu.models import MenuItemTranslation
from saleor.menu.utils import update_menu
from saleor.product import AttributeInputType, ProductAvailabilityStatus, models
from saleor.product.filters import filter_products_by_attributes_values
from saleor.product.models import (
    Attribute,
    AttributeTranslation,
    AttributeValue,
    AttributeValueTranslation,
    DigitalContentUrl,
    Product,
)
from saleor.product.thumbnails import create_product_thumbnails
from saleor.product.utils import (
    allocate_stock,
    deallocate_stock,
    decrease_stock,
    increase_stock,
)
from saleor.product.utils.attributes import associate_attribute_values_to_instance
from saleor.product.utils.availability import get_product_availability_status
from saleor.product.utils.costs import get_margin_for_variant
from saleor.product.utils.digital_products import increment_download_count
from saleor.product.utils.variants_picker import get_variant_picker_data


@pytest.mark.parametrize(
    "func, expected_quantity, expected_quantity_allocated",
    (
        (increase_stock, 150, 80),
        (decrease_stock, 50, 30),
        (deallocate_stock, 100, 30),
        (allocate_stock, 100, 130),
    ),
)
def test_stock_utils(product, func, expected_quantity, expected_quantity_allocated):
    variant = product.variants.first()
    variant.quantity = 100
    variant.quantity_allocated = 80
    variant.save()
    func(variant, 50)
    variant.refresh_from_db()
    assert variant.quantity == expected_quantity
    assert variant.quantity_allocated == expected_quantity_allocated


def test_product_page_redirects_to_correct_slug(client, product):
    uri = product.get_absolute_url()
    uri = uri.replace(product.get_slug(), "spanish-inquisition")
    response = client.get(uri)
    assert response.status_code == 301
    location = response["location"]
    if location.startswith("http"):
        location = location.split("http://testserver")[1]
    assert location == product.get_absolute_url()


def test_product_preview(admin_client, client, product):
    product.publication_date = datetime.date.today() + datetime.timedelta(days=7)
    product.save()
    response = client.get(product.get_absolute_url())
    assert response.status_code == 404
    response = admin_client.get(product.get_absolute_url())
    assert response.status_code == 200


def test_filtering_by_attribute(db, color_attribute, category, settings):
    product_type_a = models.ProductType.objects.create(
        name="New class", has_variants=True
    )
    product_type_a.product_attributes.add(color_attribute)
    product_type_b = models.ProductType.objects.create(
        name="New class", has_variants=True
    )
    product_type_b.variant_attributes.add(color_attribute)
    product_a = models.Product.objects.create(
        name="Test product a",
        price=Money(10, settings.DEFAULT_CURRENCY),
        product_type=product_type_a,
        category=category,
    )
    models.ProductVariant.objects.create(product=product_a, sku="1234")
    product_b = models.Product.objects.create(
        name="Test product b",
        price=Money(10, settings.DEFAULT_CURRENCY),
        product_type=product_type_b,
        category=category,
    )
    variant_b = models.ProductVariant.objects.create(product=product_b, sku="12345")
    color = color_attribute.values.first()
    color_2 = color_attribute.values.last()

    # Associate color to a product and a variant
    associate_attribute_values_to_instance(product_a, color_attribute, color)
    associate_attribute_values_to_instance(variant_b, color_attribute, color)

    product_qs = models.Product.objects.all().values_list("pk", flat=True)

    filters = {color_attribute.pk: [color.pk]}
    filtered = filter_products_by_attributes_values(product_qs, filters)
    assert product_a.pk in list(filtered)
    assert product_b.pk in list(filtered)

    associate_attribute_values_to_instance(product_a, color_attribute, color_2)

    filters = {color_attribute.pk: [color.pk]}
    filtered = filter_products_by_attributes_values(product_qs, filters)

    assert product_a.pk not in list(filtered)
    assert product_b.pk in list(filtered)

    filters = {color_attribute.pk: [color_2.pk]}
    filtered = filter_products_by_attributes_values(product_qs, filters)
    assert product_a.pk in list(filtered)
    assert product_b.pk not in list(filtered)

    # Filter by multiple values, should trigger a OR condition
    filters = {color_attribute.pk: [color.pk, color_2.pk]}
    filtered = filter_products_by_attributes_values(product_qs, filters)
    assert product_a.pk in list(filtered)
    assert product_b.pk in list(filtered)


def test_render_home_page(client, product, site_settings, settings):
    # Tests if menu renders properly if none is assigned
    settings.LANGUAGE_CODE = "fr"
    site_settings.top_menu = None
    site_settings.save()

    response = client.get(reverse("home"))
    assert response.status_code == 200


def test_render_home_page_with_translated_menu_items(
    client, product, menu_with_items, site_settings, settings
):
    settings.LANGUAGE_CODE = "fr"
    site_settings.top_menu = menu_with_items
    site_settings.save()

    for item in menu_with_items.items.all():
        MenuItemTranslation.objects.create(
            menu_item=item, language_code="fr", name="Translated name in French"
        )
    update_menu(menu_with_items)

    response = client.get(reverse("home"))
    assert response.status_code == 200
    assert "Translated name in French" in str(response.content)


def test_render_home_page_with_sale(client, product, sale):
    response = client.get(reverse("home"))
    assert response.status_code == 200


def test_render_home_page_with_taxes(client, product):
    response = client.get(reverse("home"))
    assert response.status_code == 200


def test_render_category(client, category, product):
    response = client.get(category.get_absolute_url())
    assert response.status_code == 200


def test_render_category_with_sale(client, category, product, sale):
    response = client.get(category.get_absolute_url())
    assert response.status_code == 200


def test_render_category_with_taxes(client, category, product):
    response = client.get(category.get_absolute_url())
    assert response.status_code == 200


def test_render_product_detail(client, product):
    response = client.get(product.get_absolute_url())
    assert response.status_code == 200


def test_render_product_detail_with_sale(client, product, sale):
    response = client.get(product.get_absolute_url())
    assert response.status_code == 200


def test_render_product_detail_with_taxes(client, product):
    response = client.get(product.get_absolute_url())
    assert response.status_code == 200


def test_view_invalid_add_to_checkout(client, product, request_checkout):
    variant = product.variants.get()
    add_variant_to_checkout(request_checkout, variant, 2)
    response = client.post(
        reverse(
            "product:add-to-checkout",
            kwargs={"slug": product.get_slug(), "product_id": product.pk},
        ),
        {},
    )
    assert response.status_code == 200
    assert request_checkout.quantity == 2


def test_view_add_to_checkout_invalid_variant(client, product, request_checkout):
    response = client.post(
        reverse(
            "product:add-to-checkout",
            kwargs={"slug": product.get_slug(), "product_id": product.pk},
        ),
        {"variant": 1234, "quantity": 1},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert response.status_code == 400
    assert request_checkout.quantity == 0


def test_view_add_to_checkout(authorized_client, product, user_checkout):
    variant = product.variants.first()

    # Ignore stock
    variant.track_inventory = False
    variant.save()

    # Add the variant to the user checkout and retrieve the variant line
    add_variant_to_checkout(user_checkout, variant)
    checkout_line = user_checkout.lines.last()

    # Retrieve the test url
    checkout_url = reverse(
        "product:add-to-checkout",
        kwargs={"slug": product.get_slug(), "product_id": product.pk},
    )

    # Attempt to set the quantity to 50
    response = authorized_client.post(
        checkout_url,
        {"quantity": 49, "variant": variant.pk},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )  # type: JsonResponse
    assert response.status_code == 200

    # Ensure the line quantity was updated to 50
    checkout_line.refresh_from_db(fields=["quantity"])
    assert checkout_line.quantity == 50

    # Attempt to increase the quantity to a too high count
    response = authorized_client.post(
        checkout_url,
        {"quantity": 1, "variant": variant.pk},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert response.status_code == 400

    # Ensure the line quantity was not updated to 51
    checkout_line.refresh_from_db(fields=["quantity"])
    assert checkout_line.quantity == 50


def test_adding_to_checkout_with_current_user_token(
    customer_user, authorized_client, product, request_checkout_with_item
):
    key = utils.COOKIE_NAME
    request_checkout_with_item.user = customer_user
    request_checkout_with_item.save()

    response = authorized_client.get(reverse("checkout:index"))

    utils.set_checkout_cookie(request_checkout_with_item, response)
    authorized_client.cookies[key] = response.cookies[key]
    variant = request_checkout_with_item.lines.first().variant
    url = reverse(
        "product:add-to-checkout",
        kwargs={"slug": product.get_slug(), "product_id": product.pk},
    )
    data = {"quantity": 1, "variant": variant.pk}

    authorized_client.post(url, data)

    assert Checkout.objects.count() == 1
    assert Checkout.objects.get(user=customer_user).pk == request_checkout_with_item.pk


def test_adding_to_checkout_with_another_user_token(
    admin_user, admin_client, product, customer_user, request_checkout_with_item
):
    client = admin_client
    key = utils.COOKIE_NAME
    request_checkout_with_item.user = customer_user
    request_checkout_with_item.save()

    response = client.get(reverse("checkout:index"))

    utils.set_checkout_cookie(request_checkout_with_item, response)
    client.cookies[key] = response.cookies[key]
    variant = request_checkout_with_item.lines.first().variant
    url = reverse(
        "product:add-to-checkout",
        kwargs={"slug": product.get_slug(), "product_id": product.pk},
    )
    data = {"quantity": 1, "variant": variant.pk}

    client.post(url, data)

    assert Checkout.objects.count() == 2
    assert Checkout.objects.get(user=admin_user).pk != request_checkout_with_item.pk


def test_anonymous_adding_to_checkout_with_another_user_token(
    client, product, customer_user, request_checkout_with_item
):
    key = utils.COOKIE_NAME
    request_checkout_with_item.user = customer_user
    request_checkout_with_item.save()

    response = client.get(reverse("checkout:index"))

    utils.set_checkout_cookie(request_checkout_with_item, response)
    client.cookies[key] = response.cookies[key]
    variant = product.variants.get()
    url = reverse(
        "product:add-to-checkout",
        kwargs={"slug": product.get_slug(), "product_id": product.pk},
    )
    data = {"quantity": 1, "variant": variant.pk}

    client.post(url, data)

    assert Checkout.objects.count() == 2
    assert Checkout.objects.get(user=None).pk != request_checkout_with_item.pk


def test_adding_to_checkout_with_deleted_checkout_token(
    customer_user, authorized_client, product, request_checkout_with_item
):
    key = utils.COOKIE_NAME
    request_checkout_with_item.user = customer_user
    request_checkout_with_item.save()
    old_token = request_checkout_with_item.token

    response = authorized_client.get(reverse("checkout:index"))

    utils.set_checkout_cookie(request_checkout_with_item, response)
    authorized_client.cookies[key] = response.cookies[key]
    request_checkout_with_item.delete()
    variant = product.variants.get()
    url = reverse(
        "product:add-to-checkout",
        kwargs={"slug": product.get_slug(), "product_id": product.pk},
    )
    data = {"quantity": 1, "variant": variant.pk}

    authorized_client.post(url, data)

    assert Checkout.objects.count() == 1
    assert not Checkout.objects.filter(token=old_token).exists()


def test_adding_to_checkout_with_closed_checkout_token(
    customer_user, authorized_client, product, request_checkout_with_item
):
    key = utils.COOKIE_NAME
    request_checkout_with_item.user = customer_user
    request_checkout_with_item.save()

    response = authorized_client.get(reverse("checkout:index"))
    utils.set_checkout_cookie(request_checkout_with_item, response)
    authorized_client.cookies[key] = response.cookies[key]
    variant = product.variants.get()
    url = reverse(
        "product:add-to-checkout",
        kwargs={"slug": product.get_slug(), "product_id": product.pk},
    )
    data = {"quantity": 1, "variant": variant.pk}

    authorized_client.post(url, data)

    assert customer_user.checkouts.count() == 1


def test_product_filter_before_filtering(authorized_client, product, category):
    products = (
        models.Product.objects.all()
        .filter(category__name=category)
        .order_by("-price_amount")
    )
    url = reverse(
        "product:category", kwargs={"slug": category.slug, "category_id": category.pk}
    )

    response = authorized_client.get(url)

    assert list(products) == list(response.context["filter_set"].qs)


def test_product_filter_product_exists(authorized_client, product, category):
    products = (
        models.Product.objects.all()
        .filter(category__name=category)
        .order_by("-price_amount")
    )
    url = reverse(
        "product:category", kwargs={"slug": category.slug, "category_id": category.pk}
    )
    data = {
        "minimal_variant_price_amount_min": [""],
        "minimal_variant_price_amount_max": ["20"],
    }

    response = authorized_client.get(url, data)

    assert list(response.context["filter_set"].qs) == list(products)


def test_product_filter_multi_values_attribute(
    authorized_client, product_with_multiple_values_attributes, category
):
    """This tests the filters against multiple values attributes.

    It ensures:
        - It can filter by selecting multiple values
        - It can filter by selecting only one value
        - Having no occurrence can actually happen
    """

    product = product_with_multiple_values_attributes
    product_type = product.product_type
    attribute = product_type.product_attributes.first()
    attribute_values = attribute.values.in_bulk()  # type: dict

    url = reverse(
        "product:category", kwargs={"slug": category.slug, "category_id": category.pk}
    )

    # Try selecting all the values
    data = {"modes": list(attribute_values.keys())}
    response = authorized_client.get(url, data)
    assert list(response.context["filter_set"].qs) == [product]

    # Try filtering with only one value
    data["modes"].pop()
    response = authorized_client.get(url, data)
    assert list(response.context["filter_set"].qs) == [product]

    # Try filtering with no occurrence
    attr_product_assoc = product.attributes.get(assignment__attribute_id=attribute.pk)
    attr_product_assoc.values.remove(data["modes"][0])
    response = authorized_client.get(url, data)
    assert list(response.context["filter_set"].qs) == []


def test_product_filter_non_filterable(
    authorized_client,
    product_with_multiple_values_attributes,
    category,
    product_list_published,
):
    """Ensures one cannot filter using a non filterable attribute"""

    product = product_with_multiple_values_attributes
    product_type = product.product_type
    attribute = product_type.product_attributes.first()
    attribute_values = attribute.values.in_bulk()  # type: dict
    attribute.filterable_in_storefront = False
    attribute.save(update_fields=["filterable_in_storefront"])

    url = reverse(
        "product:category", kwargs={"slug": category.slug, "category_id": category.pk}
    )

    # Try selecting by the disabled attribute
    data = {"modes": list(attribute_values.keys())}
    response = authorized_client.get(url, data)

    # Nothing should have been filtered, thus returning all the products
    assert list(response.context["filter_set"].qs) == list(Product.objects.all())


def test_product_filter_handles_garbage_input(
    authorized_client,
    product_with_multiple_values_attributes,
    category,
    product_list_published,
):
    """Ensure filtering products through an invalid ID (non integer input) doesn't
    trigger any crash or error.
    """

    url = reverse(
        "product:category", kwargs={"slug": category.slug, "category_id": category.pk}
    )

    # Try selecting by the disabled attribute
    data = {"modes": "123-invalid-pk"}
    response = authorized_client.get(url, data)
    assert response.status_code == 200

    # Nothing should have been filtered, thus returning all the products
    assert list(response.context["filter_set"].qs) == list(Product.objects.all())


def test_product_filter_product_does_not_exist(authorized_client, product, category):
    url = reverse(
        "product:category", kwargs={"slug": category.slug, "category_id": category.pk}
    )
    data = {"minimal_variant_price_min": ["20"], "minimal_variant_price_max": [""]}

    response = authorized_client.get(url, data)

    assert not list(response.context["filter_set"].qs)


def test_product_filter_form(authorized_client, product, category):
    products = (
        models.Product.objects.all()
        .filter(category__name=category)
        .order_by("-minimal_variant_price_amount")
    )
    url = reverse(
        "product:category", kwargs={"slug": category.slug, "category_id": category.pk}
    )

    response = authorized_client.get(url)

    assert "minimal_variant_price" in response.context["filter_set"].form.fields.keys()
    assert "sort_by" in response.context["filter_set"].form.fields.keys()
    assert list(response.context["filter_set"].qs) == list(products)


def test_product_filter_sorted_by_price_descending(
    authorized_client, product_list, category
):
    products = (
        models.Product.objects.all()
        .filter(category__name=category, is_published=True)
        .order_by("-minimal_variant_price_amount")
    )
    url = reverse(
        "product:category", kwargs={"slug": category.slug, "category_id": category.pk}
    )
    data = {"sort_by": "-minimal_variant_price_amount"}

    response = authorized_client.get(url, data)

    assert list(response.context["filter_set"].qs) == list(products)


def test_product_filter_sorted_by_wrong_parameter(authorized_client, product, category):
    url = reverse(
        "product:category", kwargs={"slug": category.slug, "category_id": category.pk}
    )
    data = {"sort_by": "aaa"}

    response = authorized_client.get(url, data)

    assert not response.context["filter_set"].form.is_valid()
    assert not response.context["products"]


def test_get_variant_picker_data_proper_variant_count(product):
    data = get_variant_picker_data(
        product, discounts=None, extensions=None, local_currency=None
    )

    assert len(data["variantAttributes"][0]["values"]) == 1


def test_get_variant_picker_data_no_nested_attributes(variant, product_type, category):
    """Ensures that if someone bypassed variant attributes checks (e.g. a raw SQL query)
    and inserted an attribute with multiple values, it doesn't return invalid data
    to the storefront that would crash it."""

    variant_attr = Attribute.objects.create(
        slug="modes", name="Available Modes", input_type=AttributeInputType.MULTISELECT
    )

    attr_val_1 = AttributeValue.objects.create(
        attribute=variant_attr, name="Eco Mode", slug="eco"
    )
    attr_val_2 = AttributeValue.objects.create(
        attribute=variant_attr, name="Performance Mode", slug="power"
    )

    product_type.variant_attributes.clear()
    product_type.variant_attributes.add(variant_attr)

    associate_attribute_values_to_instance(
        variant, variant_attr, attr_val_1, attr_val_2
    )

    product = variant.product
    data = get_variant_picker_data(product, discounts=None, local_currency=None)

    assert len(data["variantAttributes"]) == 0


def test_render_product_page_with_no_variant(unavailable_product, admin_client):
    product = unavailable_product
    product.is_published = True
    product.product_type.has_variants = True
    product.save()
    status = get_product_availability_status(product)
    assert status == ProductAvailabilityStatus.VARIANTS_MISSSING
    url = reverse(
        "product:details", kwargs={"product_id": product.pk, "slug": product.get_slug()}
    )
    response = admin_client.get(url)
    assert response.status_code == 200


def test_render_product_page_with_multi_values_attribute(
    client, product_with_multiple_values_attributes
):
    """This test ensures the rendering of a product without attribute doesn't fail."""
    product = product_with_multiple_values_attributes
    url = reverse(
        "product:details", kwargs={"product_id": product.pk, "slug": product.get_slug()}
    )
    response = client.get(url)
    assert response.status_code == 200


def test_product_page_renders_attributes_properly(
    settings, client, product_with_multiple_values_attributes, color_attribute
):
    """This test ensures the product attributes are properly rendered as expected
    including the translations."""

    settings.LANGUAGE_CODE = "fr"

    product = product_with_multiple_values_attributes
    multi_values_attribute = product.product_type.product_attributes.first()

    # Retrieve the attributes' values
    red, blue = color_attribute.values.all()
    eco_mode, performance_mode = multi_values_attribute.values.all()

    # Assign the dropdown attribute to the product
    product.product_type.product_attributes.add(color_attribute)
    associate_attribute_values_to_instance(product, color_attribute, red)

    # Create the attribute name translations
    AttributeTranslation.objects.bulk_create(
        [
            AttributeTranslation(
                language_code="fr",
                attribute=multi_values_attribute,
                name="Multiple Valeurs",
            ),
            AttributeTranslation(
                language_code="fr", attribute=color_attribute, name="Couleur"
            ),
        ]
    )

    # Create the attribute value translations
    AttributeValueTranslation.objects.bulk_create(
        [
            AttributeValueTranslation(
                language_code="fr", attribute_value=red, name="Rouge"
            ),
            AttributeValueTranslation(
                language_code="fr", attribute_value=blue, name="Bleu"
            ),
            AttributeValueTranslation(
                language_code="fr", attribute_value=eco_mode, name="Mode économique"
            ),
            AttributeValueTranslation(
                language_code="fr",
                attribute_value=performance_mode,
                name="Mode performance",
            ),
        ]
    )

    # Render the page
    url = reverse(
        "product:details", kwargs={"product_id": product.pk, "slug": product.get_slug()}
    )
    response = client.get(url)  # type: TemplateResponse
    assert response.status_code == 200

    # Retrieve the attribute table
    soup = BeautifulSoup(response.content, "lxml")
    attribute_table = soup.select_one(".product__info table")  # type: Tag
    assert attribute_table, "Did not find the attribute table"

    # Retrieve the table rows
    expected_attributes_re = re.compile(
        r"Multiple Valeurs:Mode économique,\s+Mode performance\n\s*"  # noqa: no black!
        r"Couleur:Rouge"
    )

    attribute_rows = attribute_table.select("tr")
    actual_attributes = "\n".join(row.get_text(strip=True) for row in attribute_rows)

    assert len(attribute_rows) == 2
    assert expected_attributes_re.match(actual_attributes)


def test_include_products_from_subcategories_in_main_view(
    category, product, authorized_client
):
    subcategory = models.Category.objects.create(
        name="sub", slug="test", parent=category
    )
    product.category = subcategory
    product.save()
    # URL to parent category view
    url = reverse(
        "product:category", kwargs={"slug": category.slug, "category_id": category.pk}
    )
    response = authorized_client.get(url)
    assert product in response.context_data["products"][0]


@patch("saleor.product.thumbnails.create_thumbnails")
def test_create_product_thumbnails(mock_create_thumbnails, product_with_image):
    product_image = product_with_image.images.first()
    create_product_thumbnails(product_image.pk)
    assert mock_create_thumbnails.called_once_with(
        product_image.pk, models.ProductImage, "products"
    )


@pytest.mark.parametrize(
    "expected_price, include_discounts",
    [(Decimal("10.00"), True), (Decimal("15.0"), False)],
)
def test_get_price(
    product_type,
    category,
    sale,
    expected_price,
    include_discounts,
    site_settings,
    discount_info,
):
    product = models.Product.objects.create(
        product_type=product_type,
        category=category,
        price=Money(Decimal("15.00"), "USD"),
    )
    variant = product.variants.create()

    price = variant.get_price(discounts=[discount_info] if include_discounts else [])

    assert price.amount == expected_price


def test_product_get_price_variant_has_no_price(product_type, category, site_settings):
    site_settings.include_taxes_in_prices = False
    site_settings.save()
    product = models.Product.objects.create(
        product_type=product_type, category=category, price=Money("10.00", "USD")
    )
    variant = product.variants.create()

    price = variant.get_price()

    assert price == Money("10.00", "USD")


def test_product_get_price_variant_with_price(product_type, category):
    product = models.Product.objects.create(
        product_type=product_type, category=category, price=Money("10.00", "USD")
    )
    variant = product.variants.create(price_override=Money("20.00", "USD"))

    price = variant.get_price()

    assert price == Money("20.00", "USD")


def test_product_get_price_range_with_variants(product_type, category):
    product = models.Product.objects.create(
        product_type=product_type, category=category, price=Money("15.00", "USD")
    )
    product.variants.create(sku="1")
    product.variants.create(sku="2", price_override=Money("20.00", "USD"))
    product.variants.create(sku="3", price_override=Money("11.00", "USD"))

    price = product.get_price_range()

    start = Money("11.00", "USD")
    stop = Money("20.00", "USD")
    assert price == MoneyRange(start=start, stop=stop)


def test_product_get_price_range_no_variants(product_type, category):
    product = models.Product.objects.create(
        product_type=product_type, category=category, price=Money("10.00", "USD")
    )

    price = product.get_price_range()

    expected_price = Money("10.00", "USD")
    assert price == MoneyRange(start=expected_price, stop=expected_price)


def test_product_get_price_do_not_charge_taxes(product_type, category, discount_info):
    product = models.Product.objects.create(
        product_type=product_type,
        category=category,
        price=Money("10.00", "USD"),
        charge_taxes=False,
    )
    variant = product.variants.create()

    price = variant.get_price(discounts=[discount_info])

    assert price == Money("5.00", "USD")


def test_product_get_price_range_do_not_charge_taxes(
    product_type, category, discount_info
):
    product = models.Product.objects.create(
        product_type=product_type,
        category=category,
        price=Money("10.00", "USD"),
        charge_taxes=False,
    )

    price = product.get_price_range(discounts=[discount_info])

    expected_price = MoneyRange(start=Money("5.00", "USD"), stop=Money("5.00", "USD"))
    assert price == expected_price


@pytest.mark.parametrize("price_override", ["15.00", "0.00"])
def test_variant_base_price(product, price_override):
    variant = product.variants.get()
    assert variant.base_price == product.price

    variant.price_override = Money(price_override, "USD")
    variant.save()

    assert variant.base_price == variant.price_override


def test_variant_picker_data_with_translations(
    product, translated_variant_fr, settings
):
    settings.LANGUAGE_CODE = "fr"
    variant_picker_data = get_variant_picker_data(product)
    attribute = variant_picker_data["variantAttributes"][0]
    assert attribute["name"] == translated_variant_fr.name


def test_homepage_collection_render(client, site_settings, collection, product_list):
    collection.products.add(*product_list)
    site_settings.homepage_collection = collection
    site_settings.save()

    response = client.get(reverse("home"))
    assert response.status_code == 200
    products_in_context = {product[0] for product in response.context["products"]}
    products_available = {product for product in product_list if product.is_published}
    assert products_in_context == products_available


def test_digital_product_view(client, digital_content_url):
    """Ensure a user (anonymous or not) can download a non-expired digital good
    using its associated token and that all associated events
    are correctly generated."""

    url = digital_content_url.get_absolute_url()
    response = client.get(url)
    filename = os.path.basename(digital_content_url.content.content_file.name)

    assert response.status_code == 200
    assert response["content-type"] == "image/jpeg"
    assert response["content-disposition"] == 'attachment; filename="%s"' % filename

    # Ensure an event was generated from downloading a digital good.
    # The validity of this event is checked in test_digital_product_increment_download
    assert account_events.CustomerEvent.objects.exists()


@pytest.mark.parametrize(
    "is_user_null, is_line_null", ((False, False), (False, True), (True, True))
)
def test_digital_product_increment_download(
    client,
    customer_user,
    digital_content_url: DigitalContentUrl,
    is_user_null,
    is_line_null,
):
    """Ensure downloading a digital good is possible without it
    being associated to an order line/user."""

    expected_user = customer_user

    if is_line_null:
        expected_user = None
        digital_content_url.line = None
        digital_content_url.save(update_fields=["line"])
    elif is_user_null:
        expected_user = None
        digital_content_url.line.user = None
        digital_content_url.line.save(update_fields=["user"])

    expected_new_download_count = digital_content_url.download_num + 1
    increment_download_count(digital_content_url)
    assert digital_content_url.download_num == expected_new_download_count

    if expected_user is None:
        # Ensure an event was not generated from downloading a digital good
        # as no user could be found
        assert not account_events.CustomerEvent.objects.exists()
        return

    download_event = account_events.CustomerEvent.objects.get()
    assert download_event.type == account_events.CustomerEvents.DIGITAL_LINK_DOWNLOADED
    assert download_event.user == expected_user
    assert download_event.order == digital_content_url.line.order
    assert download_event.parameters == {"order_line_pk": digital_content_url.line.pk}


def test_digital_product_view_url_downloaded_max_times(client, digital_content):
    digital_content.use_default_settings = False
    digital_content.max_downloads = 1
    digital_content.save()
    digital_content_url = DigitalContentUrl.objects.create(content=digital_content)

    url = digital_content_url.get_absolute_url()
    response = client.get(url)

    # first download
    assert response.status_code == 200

    # second download
    response = client.get(url)
    assert response.status_code == 404


def test_digital_product_view_url_expired(client, digital_content):
    digital_content.use_default_settings = False
    digital_content.url_valid_days = 10
    digital_content.save()

    with freeze_time("2018-05-31 12:00:01"):
        digital_content_url = DigitalContentUrl.objects.create(content=digital_content)

    url = digital_content_url.get_absolute_url()
    response = client.get(url)

    assert response.status_code == 404


def test_variant_picker_data_price_range(product_type, category):
    product = models.Product.objects.create(
        product_type=product_type, category=category, price=Money("15.00", "USD")
    )
    product.variants.create(sku="1")
    product.variants.create(sku="2", price_override=Money("20.00", "USD"))
    product.variants.create(sku="3", price_override=Money("11.00", "USD"))

    start = TaxedMoney(net=Money("11.00", "USD"), gross=Money("11.00", "USD"))
    stop = TaxedMoney(net=Money("20.00", "USD"), gross=Money("20.00", "USD"))

    picker_data = get_variant_picker_data(product, discounts=None, local_currency=None)

    min_price = picker_data["availability"]["priceRange"]["minPrice"]
    min_price = TaxedMoney(
        net=Money(min_price["net"], min_price["currency"]),
        gross=Money(min_price["gross"], min_price["currency"]),
    )

    max_price = picker_data["availability"]["priceRange"]["maxPrice"]
    max_price = TaxedMoney(
        net=Money(max_price["net"], max_price["currency"]),
        gross=Money(max_price["gross"], max_price["currency"]),
    )

    assert min_price == start
    assert max_price == stop


@pytest.mark.parametrize(
    "price, cost", [(Money("0", "USD"), Money("1", "USD")), (Money("2", "USD"), None)]
)
def test_costs_get_margin_for_variant(variant, price, cost):
    variant.cost_price = cost
    variant.price_override = price
    assert not get_margin_for_variant(variant)
