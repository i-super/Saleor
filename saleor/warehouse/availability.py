from collections import defaultdict
from typing import TYPE_CHECKING, Dict

from django.conf import settings
from django.db.models import Sum
from django.db.models.functions import Coalesce

from ..core.exceptions import InsufficientStock
from .models import Stock, StockQuerySet

if TYPE_CHECKING:
    from ..product.models import Product, ProductVariant


def _get_quantity_allocated(stocks: StockQuerySet) -> int:
    return stocks.aggregate(
        quantity_allocated=Coalesce(Sum("allocations__quantity_allocated"), 0)
    )["quantity_allocated"]


def _get_available_quantity(stocks: StockQuerySet) -> int:
    results = stocks.aggregate(
        total_quantity=Coalesce(Sum("quantity", distinct=True), 0),
        quantity_allocated=Coalesce(Sum("allocations__quantity_allocated"), 0),
    )
    total_quantity = results["total_quantity"]
    quantity_allocated = results["quantity_allocated"]

    return max(total_quantity - quantity_allocated, 0)


def check_stock_quantity(variant: "ProductVariant", country_code: str, quantity: int):
    """Validate if there is stock available for given variant in given country.

    If so - returns None. If there is less stock then required raise InsufficientStock
    exception.
    """
    if variant.track_inventory:
        stocks = Stock.objects.get_variant_stocks_for_country(country_code, variant)
        if not stocks:
            raise InsufficientStock(variant)

        if quantity > _get_available_quantity(stocks):
            raise InsufficientStock(variant)


def get_available_quantity(variant: "ProductVariant", country_code: str) -> int:
    """Return available quantity for given product in given country."""
    stocks = Stock.objects.get_variant_stocks_for_country(country_code, variant)
    if not stocks:
        return 0
    return _get_available_quantity(stocks)


def get_available_quantity_for_customer(
    variant: "ProductVariant", country_code: str = None
) -> int:
    """Return maximum checkout line quantity.

    Returns maximum checkout quantity for the given variant and country code.
    If country code is provided, the function returns the exact variant quantity
    available in warehouses operating in shipping zones containing this country.
    Otherwise, it returns the maximum quantity from all shipping zones.

    The returned value is limited by `MAX_CHECKOUT_LINE_QUANTITY` setting to
    limit the quantity of a variant that can be added in one checkout line.
    """
    if not variant.track_inventory:
        return settings.MAX_CHECKOUT_LINE_QUANTITY

    stocks = Stock.objects.filter(product_variant=variant)
    if country_code:
        stocks = stocks.for_country(country_code)
    stocks = stocks.annotate_available_quantity()
    stocks = stocks.values_list("warehouse__shipping_zones", "available_quantity")

    if not stocks:
        return 0

    available_quantity_in_shipping_zones: Dict = defaultdict(int)
    for shipping_zone_pk, available_quantity in stocks:
        available_quantity_in_shipping_zones[shipping_zone_pk] += available_quantity

    max_available_quantity = max(
        available_quantity_in_shipping_zones.items(), key=lambda x: x[1]
    )[1]
    return min(max_available_quantity, settings.MAX_CHECKOUT_LINE_QUANTITY)


def get_quantity_allocated(variant: "ProductVariant", country_code: str) -> int:
    stocks = Stock.objects.get_variant_stocks_for_country(country_code, variant)
    if not stocks:
        return 0
    return _get_quantity_allocated(stocks)


def is_variant_in_stock(variant: "ProductVariant", country_code: str) -> bool:
    """Check if variant is available in given country."""
    quantity_available = get_available_quantity_for_customer(variant, country_code)
    return quantity_available > 0


def is_product_in_stock(product: "Product", country_code: str) -> bool:
    """Check if there is any variant of given product available in given country."""
    stocks = Stock.objects.get_product_stocks_for_country(
        country_code, product
    ).annotate_available_quantity()
    return any(stocks.values_list("available_quantity", flat=True))


def are_all_product_variants_in_stock(product: "Product", country_code: str) -> bool:
    """Check if all variants of given product are available in given country."""
    stocks = Stock.objects.get_product_stocks_for_country(
        country_code, product
    ).annotate_available_quantity()
    stocks = stocks.values_list("available_quantity", "product_variant_id").all()
    are_all_available = all([elem[0] for elem in stocks])
    variants_with_stocks = [elem[1] for elem in stocks]

    product_variants = product.variants.exclude(id__in=variants_with_stocks).exists()
    return are_all_available and not product_variants
