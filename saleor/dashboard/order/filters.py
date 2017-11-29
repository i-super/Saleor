from __future__ import unicode_literals

from django_filters import (
    CharFilter, ChoiceFilter, DateFromToRangeFilter, FilterSet, RangeFilter,
    OrderingFilter)
from django.utils.translation import pgettext_lazy
from django_prices.models import PriceField
from payments import PaymentStatus

from ...core.utils.filters import filter_by_customer
from ...order.models import Order
from ..widgets import DateRangeWidget


SORT_BY_FIELDS = (
    ('pk', 'pk'),
    ('status', 'status'),
    ('payments__status', 'payment_status'),
    ('user__email', 'email'),
    ('created', 'created'),
    ('total_net', 'total')
)

SORT_BY_FIELDS_LABELS = {
    'pk': pgettext_lazy('Order list sorting option', '#'),
    'status': pgettext_lazy('Order list sorting option', 'status'),
    'payments__status': pgettext_lazy('Order list sorting option', 'payment'),
    'user__email': pgettext_lazy('Order list sorting option', 'email'),
    'created': pgettext_lazy('Order list sorting option', 'created'),
    'total_net': pgettext_lazy('Order list sorting option', 'created')}


class OrderFilter(FilterSet):
    name_or_email = CharFilter(
        label=pgettext_lazy('Customer name or email filter', 'Name or email'),
        method=filter_by_customer)
    sort_by = OrderingFilter(
        label=pgettext_lazy('Order list sorting filter', 'Sort by'),
        fields=SORT_BY_FIELDS,
        field_labels=SORT_BY_FIELDS_LABELS)
    payment_status = ChoiceFilter(
        label=pgettext_lazy('Order list sorting filter', 'Payment status'),
        name='payments__status', choices=PaymentStatus.CHOICES)
    created = DateFromToRangeFilter(
        label=pgettext_lazy('Order list sorting filter', 'Placed on'),
        name='created', widget=DateRangeWidget)

    class Meta:
        model = Order
        fields = ['status', 'created', 'total_net']
        filter_overrides = {
            PriceField: {
                'filter_class': RangeFilter
            }
        }
