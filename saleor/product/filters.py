from __future__ import unicode_literals
from collections import OrderedDict

from django_filters import (FilterSet, MultipleChoiceFilter, RangeFilter,
                            OrderingFilter)
from django.forms import CheckboxSelectMultiple
from django.utils.translation import pgettext_lazy

from django_prices.models import PriceField

from .models import Product, ProductAttribute

# SORT_BY_FIELDS = (('name', pgettext_lazy('Sort by filter', 'name')),
#                   ('price', pgettext_lazy()))

SORT_BY_FIELDS = [{'value': 'name',
                   'label': pgettext_lazy('Sort by filter', 'name')},
                  {'value': 'price',
                   'label': pgettext_lazy('Sort by filter', 'price')}]


class ProductFilter(FilterSet):
    def __init__(self, *args, **kwargs):
        self.category = kwargs.pop('category')
        super(ProductFilter, self).__init__(*args, **kwargs)
        self.product_attributes, self.variant_attributes = \
            self._get_attributes(self.category)
        self._add_product_attributes_filters()
        self._add_product_variants_attributes_filters()
        self.filters = OrderedDict(sorted(self.filters.items()))

    sort_by = OrderingFilter(
        label='Sort by',
        fields=[(field['value'], field['value']) for field in SORT_BY_FIELDS]
    )

    class Meta:
        model = Product
        fields = ['price']
        filter_overrides = {
            PriceField: {
                'filter_class': RangeFilter
            }
        }

    def _get_attributes(self, category):
        product_attributes = \
            (ProductAttribute.objects.all()
             .prefetch_related('values')
             .filter(products_class__products__categories=category)
             .distinct())
        variant_attributes = \
            (ProductAttribute.objects.all()
             .prefetch_related('values')
             .filter(product_variants_class__products__categories=category)
             .distinct())
        return product_attributes, variant_attributes

    def _add_product_attributes_filters(self):
        for attribute in self.product_attributes:
            self.filters[attribute.slug] = MultipleChoiceFilter(
                name='attributes__%s' % attribute.pk,
                label=attribute.name,
                widget=CheckboxSelectMultiple,
                choices=self._get_attribute_choices(attribute))

    def _add_product_variants_attributes_filters(self):
        for attribute in self.variant_attributes:
            self.filters[attribute.slug] = MultipleChoiceFilter(
                name='variants__attributes__%s' % attribute.pk,
                label=attribute.name,
                widget=CheckboxSelectMultiple,
                choices=self._get_attribute_choices(attribute))

    def _get_attribute_choices(self, attribute):
        return [(choice.pk, choice.name) for choice in attribute.values.all()]
