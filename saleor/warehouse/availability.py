from collections import defaultdict
from typing import TYPE_CHECKING, Dict, Iterable, List

from django.db.models import Sum
from django.db.models.functions import Coalesce

from ..core.exceptions import InsufficientStock, InsufficientStockData
from .models import Stock, StockQuerySet

if TYPE_CHECKING:
    from ..product.models import Product, ProductVariant


def _get_available_quantity(stocks: StockQuerySet) -> int:
    results = stocks.aggregate(
        total_quantity=Coalesce(Sum("quantity", distinct=True), 0),
        quantity_allocated=Coalesce(Sum("allocations__quantity_allocated"), 0),
    )
    total_quantity = results["total_quantity"]
    quantity_allocated = results["quantity_allocated"]

    return max(total_quantity - quantity_allocated, 0)


def check_stock_quantity(
    variant: "ProductVariant", country_code: str, channel_slug: str, quantity: int
):
    """Validate if there is stock available for given variant in given country.

    If so - returns None. If there is less stock then required raise InsufficientStock
    exception.
    """
    if variant.track_inventory:
        stocks = Stock.objects.get_variant_stocks_for_country(
            country_code, channel_slug, variant
        )
        if not stocks:
            raise InsufficientStock([InsufficientStockData(variant=variant)])

        if quantity > _get_available_quantity(stocks):
            raise InsufficientStock([InsufficientStockData(variant=variant)])


def check_stock_quantity_bulk(
    variants: Iterable["ProductVariant"],
    country_code: str,
    quantities: Iterable[int],
    channel_slug: str,
):
    """Validate if there is stock available for given variants in given country.

    :raises InsufficientStock: when there is not enough items in stock for a variant.
    """
    all_variants_stocks = (
        Stock.objects.for_country_and_channel(country_code, channel_slug)
        .filter(product_variant__in=variants)
        .annotate_available_quantity()
    )

    variant_stocks: Dict[int, List[Stock]] = defaultdict(list)
    for stock in all_variants_stocks:
        variant_stocks[stock.product_variant_id].append(stock)

    insufficient_stocks: List[InsufficientStockData] = []
    for variant, quantity in zip(variants, quantities):
        stocks = variant_stocks.get(variant.pk, [])
        available_quantity = sum(
            [stock.available_quantity for stock in stocks]  # type: ignore
        )

        if not stocks:
            insufficient_stocks.append(
                InsufficientStockData(
                    variant=variant, available_quantity=available_quantity
                )
            )
        elif variant.track_inventory:
            if quantity > available_quantity:
                insufficient_stocks.append(
                    InsufficientStockData(
                        variant=variant, available_quantity=available_quantity
                    )
                )

    if insufficient_stocks:
        raise InsufficientStock(insufficient_stocks)


def is_product_in_stock(
    product: "Product", country_code: str, channel_slug: str
) -> bool:
    """Check if there is any variant of given product available in given country."""
    stocks = Stock.objects.get_product_stocks_for_country_and_channel(
        country_code, channel_slug, product
    ).annotate_available_quantity()
    return any(stocks.values_list("available_quantity", flat=True))
