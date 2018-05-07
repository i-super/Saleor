from django.conf import settings
from prices import Money, MoneyRange

from ...core.utils import ZERO_TAXED_MONEY


def get_product_costs_data(product):
    purchase_costs_range = MoneyRange(
        start=ZERO_TAXED_MONEY, stop=ZERO_TAXED_MONEY)
    gross_margin = (0, 0)

    if not product.variants.exists():
        return purchase_costs_range, gross_margin

    variants = product.variants.all()
    costs_data = get_cost_data_from_variants(variants)
    if costs_data.costs:
        purchase_costs_range = MoneyRange(
            min(costs_data.costs), max(costs_data.costs))
    if costs_data.margins:
        gross_margin = (costs_data.margins[0], costs_data.margins[-1])
    return purchase_costs_range, gross_margin


class CostsData:
    __slots__ = ('costs', 'margins')

    def __init__(self, costs, margins):
        self.costs = sorted(costs)
        self.margins = sorted(margins)


def get_cost_data_from_variants(variants):
    costs = []
    margins = []
    for variant in variants:
        costs_data = get_variant_costs_data(variant)
        costs += costs_data.costs
        margins += costs_data.margins
    return CostsData(costs, margins)


def get_variant_costs_data(variant):
    costs = []
    margins = []
    costs.append(get_cost_price(variant))
    margin = get_margin_for_variant(variant)
    if margin:
        margins.append(margin)
    return CostsData(costs, margins)


def get_cost_price(variant):
    if not variant.cost_price:
        return Money(0, settings.DEFAULT_CURRENCY)
    return variant.cost_price


def get_margin_for_variant(variant):
    if variant.cost_price is None:
        return None
    base_price = variant.base_price
    margin = base_price - variant.cost_price
    percent = round((margin / base_price) * 100, 0)
    return percent
