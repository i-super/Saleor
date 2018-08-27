from django.utils.translation import npgettext, pgettext_lazy
from django_filters import (
    CharFilter, ChoiceFilter, OrderingFilter, RangeFilter)

from ...core.filters import SortedFilterSet
from ...core.i18n import COUNTRY_CODE_CHOICES
from ...shipping.models import ShippingZone

SORT_BY_FIELDS = {
    'name': pgettext_lazy('Group list sorting option', 'name')}


class ShippingZoneFilter(SortedFilterSet):
    name = CharFilter(
        label=pgettext_lazy(
            'Shipping zones list filter label', 'Zone name'),
        lookup_expr="icontains")
    price = RangeFilter(
        label=pgettext_lazy(
            'Shipping zones list filter label', 'Price range'),
        name='shipping_methods__price')
    country = ChoiceFilter(
        label=pgettext_lazy('Shipping zones filter label', 'Country'),
        name='countries', lookup_expr='contains',
        choices=COUNTRY_CODE_CHOICES)
    sort_by = OrderingFilter(
        label=pgettext_lazy('Product list sorting filter label', 'Sort by'),
        fields=SORT_BY_FIELDS.keys(),
        field_labels=SORT_BY_FIELDS)

    class Meta:
        model = ShippingZone
        fields = []

    def get_summary_message(self):
        counter = self.qs.count()
        return npgettext(
            'Number of matching records in the dashboard '
            'shipping methods list',
            'Found %(counter)d matching shipping method',
            'Found %(counter)d matching shipping methods',
            number=counter) % {'counter': counter}
