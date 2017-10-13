from __future__ import unicode_literals
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils.translation import pgettext, pgettext_lazy
from django.utils.encoding import python_2_unicode_compatible, smart_text
from django_countries import countries
from django_prices.models import PriceField
from django_prices.templatetags.prices_i18n import net
from prices import FixedDiscount, percentage_discount, Price

from ..cart.utils import (
    get_product_variants_and_prices, get_category_variants_and_prices)


class NotApplicable(ValueError):
    pass


class VoucherQueryset(models.QuerySet):

    def active(self):
        today = date.today()
        queryset = self.filter(
            models.Q(usage_limit__isnull=True) |
            models.Q(used__lt=models.F('usage_limit')))
        queryset = queryset.filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today))
        queryset = queryset.filter(start_date__lte=today)
        return queryset

    def increase_usage(self, voucher):
        voucher.used = F('used') + 1
        voucher.save(update_fields=['used'])

    def decrease_usage(self, voucher):
        voucher.used = F('used') - 1
        voucher.save(update_fields=['used'])


@python_2_unicode_compatible
class Voucher(models.Model):

    APPLY_TO_ONE_PRODUCT = 'one'
    APPLY_TO_ALL_PRODUCTS = 'all'

    APPLY_TO_PRODUCT_CHOICES = (
        (APPLY_TO_ONE_PRODUCT,
         pgettext_lazy('Voucher application', 'Apply to a single item')),
        (APPLY_TO_ALL_PRODUCTS,
         pgettext_lazy('Voucher application', 'Apply to all matching products')))

    DISCOUNT_VALUE_FIXED = 'fixed'
    DISCOUNT_VALUE_PERCENTAGE = 'percentage'

    DISCOUNT_VALUE_TYPE_CHOICES = (
        (DISCOUNT_VALUE_FIXED,
         pgettext_lazy('Voucher discount type', settings.DEFAULT_CURRENCY)),
        (DISCOUNT_VALUE_PERCENTAGE, pgettext_lazy('Voucher discount type', '%')))

    PRODUCT_TYPE = 'product'
    CATEGORY_TYPE = 'category'
    SHIPPING_TYPE = 'shipping'
    VALUE_TYPE = 'value'

    TYPE_CHOICES = (
        (VALUE_TYPE, pgettext_lazy('Voucher: discount for', 'All purchases')),
        (PRODUCT_TYPE, pgettext_lazy('Voucher: discount for', 'One product')),
        (CATEGORY_TYPE, pgettext_lazy('Voucher: discount for', 'A category of products')),
        (SHIPPING_TYPE, pgettext_lazy('Voucher: discount for', 'Shipping')))

    type = models.CharField(
        pgettext_lazy('Voucher field', 'discount for'), max_length=20,
        choices=TYPE_CHOICES, default=VALUE_TYPE)
    name = models.CharField(
        pgettext_lazy('Voucher field', 'name'), max_length=255, null=True,
        blank=True)
    code = models.CharField(
        pgettext_lazy('Voucher field', 'code'), max_length=12, unique=True,
        db_index=True)
    usage_limit = models.PositiveIntegerField(
        pgettext_lazy('Voucher field', 'usage limit'), null=True, blank=True)
    used = models.PositiveIntegerField(default=0, editable=False)
    start_date = models.DateField(
        pgettext_lazy('Voucher field', 'start date'), default=date.today)
    end_date = models.DateField(
        pgettext_lazy('Voucher field', 'end date'), null=True, blank=True)

    discount_value_type = models.CharField(
        pgettext_lazy('Voucher field', 'discount type'), max_length=10,
        choices=DISCOUNT_VALUE_TYPE_CHOICES, default=DISCOUNT_VALUE_FIXED)
    discount_value = models.DecimalField(
        pgettext_lazy('Voucher field', 'discount value'), max_digits=12,
        decimal_places=2)

    # not mandatory fields, usage depends on type
    product = models.ForeignKey(
        'product.Product', blank=True, null=True,
        verbose_name=pgettext_lazy('Voucher field', 'product'))
    category = models.ForeignKey(
        'product.Category', blank=True, null=True,
        verbose_name=pgettext_lazy('Voucher field', 'category'))
    apply_to = models.CharField(
        pgettext_lazy('Voucher field', 'apply to'),
        max_length=20, blank=True, null=True)
    limit = PriceField(
        pgettext_lazy('Voucher field', 'limit'),
        max_digits=12, decimal_places=2, null=True,
        blank=True, currency=settings.DEFAULT_CURRENCY)

    objects = VoucherQueryset.as_manager()

    @property
    def is_free(self):
        return (self.discount_value == Decimal(100) and
                self.discount_value_type == Voucher.DISCOUNT_VALUE_PERCENTAGE)

    class Meta:
        verbose_name = pgettext_lazy('Voucher model', 'voucher')
        verbose_name_plural = pgettext_lazy('Voucher model', 'vouchers')
        permissions = (
            ('view_voucher',
             pgettext_lazy('Permission description', 'Can view vouchers')),
            ('edit_voucher',
             pgettext_lazy('Permission description', 'Can edit vouchers')))

    def __str__(self):
        if self.name:
            return self.name
        discount = '%s %s' % (
            self.discount_value, self.get_discount_value_type_display())
        if self.type == Voucher.SHIPPING_TYPE:
            if self.is_free:
                return pgettext('Voucher type', 'Free shipping')
            else:
                return pgettext('Voucher type', '%(discount)s off shipping') % {
                    'discount': discount}
        if self.type == Voucher.PRODUCT_TYPE:
            return pgettext('Voucher type', '%(discount)s off %(product)s') % {
                'discount': discount, 'product': self.product}
        if self.type == Voucher.CATEGORY_TYPE:
            return pgettext('Voucher type', '%(discount)s off %(category)s') % {
                'discount': discount, 'category': self.category}
        return pgettext('Voucher type', '%(discount)s off') % {'discount': discount}

    def get_apply_to_display(self):
        if self.type == Voucher.SHIPPING_TYPE and self.apply_to:
            return countries.name(self.apply_to)
        if self.type == Voucher.SHIPPING_TYPE:
            return pgettext('Voucher', 'Any country')
        if self.apply_to and self.type in {
                Voucher.PRODUCT_TYPE, Voucher.CATEGORY_TYPE}:
            choices = dict(self.APPLY_TO_PRODUCT_CHOICES)
            return choices[self.apply_to]

    def get_fixed_discount_for(self, amount):
        if self.discount_value_type == self.DISCOUNT_VALUE_FIXED:
            discount_price = Price(net=self.discount_value,
                                   currency=settings.DEFAULT_CURRENCY)
            discount = FixedDiscount(
                amount=discount_price, name=smart_text(self))
        elif self.discount_value_type == self.DISCOUNT_VALUE_PERCENTAGE:
            discount = percentage_discount(
                value=self.discount_value, name=smart_text(self))
            fixed_discount_value = amount - discount.apply(amount)
            discount = FixedDiscount(
                amount=fixed_discount_value, name=smart_text(self))
        else:
            raise NotImplementedError('Unknown discount value type')
        if discount.amount > amount:
            return FixedDiscount(amount, name=smart_text(self))
        else:
            return discount

    def validate_limit(self, value):
        limit = self.limit if self.limit is not None else value
        if value < limit:
            msg = pgettext(
                'Voucher not applicable', 'This offer is only valid for orders over %(amount)s.')
            raise NotApplicable(msg % {'amount': net(limit)})

    def get_discount_for_checkout(self, checkout):
        if self.type == Voucher.VALUE_TYPE:
            cart_total = checkout.get_subtotal()
            self.validate_limit(cart_total)
            return self.get_fixed_discount_for(cart_total)

        elif self.type == Voucher.SHIPPING_TYPE:
            if not checkout.is_shipping_required:
                msg = pgettext(
                    'Voucher not applicable', 'Your order does not require shipping.')
                raise NotApplicable(msg)
            shipping_method = checkout.shipping_method
            if not shipping_method:
                msg = pgettext(
                    'Voucher not applicable', 'Please select a shipping method first.')
                raise NotApplicable(msg)
            if (self.apply_to and
                    shipping_method.country_code != self.apply_to):
                msg = pgettext(
                    'Voucher not applicable', 'This offer is only valid in %(country)s.')
                raise NotApplicable(msg % {
                    'country': self.get_apply_to_display()})
            cart_total = checkout.get_subtotal()
            self.validate_limit(cart_total)
            return self.get_fixed_discount_for(shipping_method.price)

        elif self.type in (Voucher.PRODUCT_TYPE, Voucher.CATEGORY_TYPE):
            if self.type == Voucher.PRODUCT_TYPE:
                prices = list(
                    (item[1] for item in get_product_variants_and_prices(
                        checkout.cart, self.product)))
            else:
                prices = list(
                    (item[1] for item in get_category_variants_and_prices(
                        checkout.cart, self.category)))
            if len(prices) == 0:
                msg = pgettext(
                    'Voucher not applicable',
                    'This offer is only valid for selected items.')
                raise NotApplicable(msg)
            if self.apply_to == Voucher.APPLY_TO_ALL_PRODUCTS:
                discounts = (
                    self.get_fixed_discount_for(price) for price in prices)
                discount_total = sum(
                    (discount.amount for discount in discounts),
                    Price(0, currency=settings.DEFAULT_CURRENCY))
                return FixedDiscount(discount_total, smart_text(self))
            else:
                product_total = sum(
                    prices, Price(0, currency=settings.DEFAULT_CURRENCY))
                return self.get_fixed_discount_for(product_total)

        else:
            raise NotImplementedError('Unknown discount type')


@python_2_unicode_compatible
class Sale(models.Model):
    FIXED = 'fixed'
    PERCENTAGE = 'percentage'

    DISCOUNT_TYPE_CHOICES = (
        (FIXED, pgettext_lazy('Discount type', settings.DEFAULT_CURRENCY)),
        (PERCENTAGE, pgettext_lazy('Discount type', '%')))

    name = models.CharField(pgettext_lazy('Sale (discount) field', 'name'), max_length=255)
    type = models.CharField(
        pgettext_lazy('Sale (discount) field', 'type'),
        max_length=10, choices=DISCOUNT_TYPE_CHOICES, default=FIXED)
    value = models.DecimalField(
        pgettext_lazy('Sale (discount) field', 'value'),
        max_digits=12, decimal_places=2, default=0)
    products = models.ManyToManyField(
        'product.Product', blank=True,
        verbose_name=pgettext_lazy('Sale (discount) field', 'products'))
    categories = models.ManyToManyField(
        'product.Category', blank=True,
        verbose_name=pgettext_lazy('Sale (discount) field', 'categories'))

    class Meta:
        app_label = 'discount'
        verbose_name = pgettext_lazy('Sale (discount) model', 'sale')
        verbose_name_plural = pgettext_lazy('Sales (discounts) model', 'sales')
        permissions = (
            ('view_sale',
             pgettext_lazy('Permission description', 'Can view sales')),
            ('edit_sale',
             pgettext_lazy('Permission description', 'Can edit sales')))

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

    def modifier_for_product(self, product):
        discounted_products = {p.pk for p in self.products.all()}
        discounted_categories = set(self.categories.all())
        if product.pk in discounted_products:
            return self.get_discount()
        if self._product_has_category_discount(
                product, discounted_categories):
            return self.get_discount()
        raise NotApplicable(
            pgettext(
                'Voucher not applicable', 'Discount not applicable for this product'))


def get_product_discounts(product, discounts, **kwargs):
    for discount in discounts:
        try:
            yield discount.modifier_for_product(product, **kwargs)
        except NotApplicable:
            pass


def calculate_discounted_price(product, price, discounts, **kwargs):
    if discounts:
        discounts = list(
            get_product_discounts(product, discounts, **kwargs))
        if discounts:
            price = min(price | discount for discount in discounts)
    return price
