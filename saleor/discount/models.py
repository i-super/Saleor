from __future__ import unicode_literals

from django.conf import settings
from django.db import models
from django.utils.translation import pgettext_lazy
from django.utils.encoding import python_2_unicode_compatible
from prices import FixedDiscount, percentage_discount, Price


class NotApplicable(ValueError):
    pass


@python_2_unicode_compatible
class Sale(models.Model):
    FIXED = 'fixed'
    PERCENTAGE = 'percentage'

    DISCOUNT_TYPE_CHOICES = (
        (FIXED, pgettext_lazy('discount type', 'Fixed amount')),
        (PERCENTAGE, pgettext_lazy('discount_type', 'Percentage discount')))

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES,
                            default=FIXED)
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    products = models.ManyToManyField('product.Product', blank=True)
    categories = models.ManyToManyField('product.Category', blank=True)

    class Meta:
        app_label = 'discount'

    def __repr__(self):
        return 'Sale(name=%r, value=%r, type=%s)' % (
            str(self.name), self.value, self.get_type_display())

    def __str__(self):
        return self.name

    def get_discount(self):
        if self.type == self.FIXED:
            discount_price = Price(net=self.value,
                                   currency=settings.DEFAULT_CURRENCY)
            return FixedDiscount(amount=discount_price, name=self.name)
        elif self.type == self.PERCENTAGE:
            return percentage_discount(value=self.value, name=self.name)
        raise NotImplementedError('Unknown discount type')

    def _product_has_category_discount(self, product, discounted_categories):
        for category in product.categories.all():
            for discounted_category in discounted_categories:
                if category.is_descendant_of(discounted_category,
                                             include_self=True):
                    return True
        return False

    def modifier_for_variant(self, variant):
        check_price = variant.get_price_per_item()
        discounted_products = [p.pk for p in self.products.all()]
        discounted_categories = list(self.categories.all())
        if discounted_products and variant.pk not in discounted_products:
            raise NotApplicable('Discount not applicable for this product')
        if (discounted_categories and not
                self._product_has_category_discount(
                    variant.product, discounted_categories)):
            raise NotApplicable('Discount too high for this product')
        discount = self.get_discount()
        after_discount = discount.apply(check_price)
        if after_discount.gross <= 0:
            raise NotApplicable('Discount too high for this product')
        return discount


def get_variant_discounts(variant, discounts, **kwargs):
    for discount in discounts:
        try:
            yield discount.modifier_for_variant(variant, **kwargs)
        except NotApplicable:
            pass
