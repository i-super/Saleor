from __future__ import unicode_literals

from django.conf import settings
from django.db import models
from django.utils.translation import pgettext_lazy
from django.utils.encoding import python_2_unicode_compatible
from django_prices.models import PriceField
from prices import FixedDiscount


class NotApplicable(ValueError):
    pass


@python_2_unicode_compatible
class FixedProductDiscount(models.Model):
    name = models.CharField(max_length=255)
    products = models.ManyToManyField('Product', blank=True)
    discount = PriceField(pgettext_lazy('Discount field', 'discount value'),
                          currency=settings.DEFAULT_CURRENCY,
                          max_digits=12, decimal_places=2)

    class Meta:
        app_label = 'product'

    def __repr__(self):
        return 'FixedProductDiscount(name=%r, discount=%r)' % (
            str(self.discount), self.name)

    def __str__(self):
        return self.name

    def modifier_for_product(self, variant):
        from ...product.models import ProductVariant
        if isinstance(variant, ProductVariant):
            pk = variant.product.pk
            check_price = variant.get_price_per_item()
        else:
            pk = variant.pk
            check_price = variant.get_price_per_item(variant)
        if not self.products.filter(pk=pk).exists():
            raise NotApplicable('Discount not applicable for this product')
        if self.discount > check_price:
            raise NotApplicable('Discount too high for this product')
        return FixedDiscount(self.discount, name=self.name)


def get_product_discounts(variant, discounts, **kwargs):
    for discount in discounts:
        try:
            yield discount.modifier_for_product(variant, **kwargs)
        except NotApplicable:
            pass
