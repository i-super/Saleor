import uuid

from django import forms
from django.conf import settings
from django.urls import reverse_lazy
from django.utils.translation import pgettext_lazy
from django_prices.forms import MoneyField

from ...core.i18n import COUNTRY_CODE_CHOICES
from ...core.utils.taxes import ZERO_MONEY
from ...discount import DiscountValueType
from ...discount.models import Sale, Voucher
from ...product.models import Product
from ...shipping.models import ShippingMethodCountry
from ..forms import AjaxSelect2MultipleChoiceField


class SaleForm(forms.ModelForm):
    products = AjaxSelect2MultipleChoiceField(
        queryset=Product.objects.all(),
        fetch_data_url=reverse_lazy('dashboard:ajax-products'),
        required=False,
        label=pgettext_lazy('Discounted products', 'Discounted products'))

    class Meta:
        model = Sale
        exclude = []
        labels = {
            'name': pgettext_lazy(
                'Sale name',
                'Name'),
            'type': pgettext_lazy(
                'Discount type',
                'Fixed or percentage'),
            'value': pgettext_lazy(
                'Percentage or fixed amount value',
                'Value'),
            'categories': pgettext_lazy(
                'Discounted categories',
                'Discounted categories'),
            'collections': pgettext_lazy(
                'Discounted collections',
                'Discounted collections')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['products'].set_initial(self.instance.products.all())

    def clean(self):
        cleaned_data = super().clean()
        discount_type = cleaned_data['type']
        value = cleaned_data['value']
        if discount_type == DiscountValueType.PERCENTAGE and value > 100:
            self.add_error('value', pgettext_lazy(
                'Sale (discount) error',
                'Sale cannot exceed 100%'))
        products = cleaned_data.get('products')
        categories = cleaned_data.get('categories')
        collections = cleaned_data.get('collections')
        if not any([products, categories, collections]):
            raise forms.ValidationError(pgettext_lazy(
                'Sale (discount) error',
                'A single sale must point to at least one product, collection'
                'and/or category.'))
        return cleaned_data


class VoucherForm(forms.ModelForm):

    class Meta:
        model = Voucher
        exclude = ['min_amount_spent', 'countries', 'products', 'collections', 'used']
        labels = {
            'type': pgettext_lazy(
                'Discount type',
                'Discount type'),
            'name': pgettext_lazy(
                'Item name',
                'Name'),
            'code': pgettext_lazy(
                'Coupon code',
                'Code'),
            'usage_limit': pgettext_lazy(
                'Usage limit',
                'Usage limit'),
            'start_date': pgettext_lazy(
                'Voucher date restrictions',
                'Start date'),
            'end_date': pgettext_lazy(
                'Voucher date restrictions',
                'End date'),
            'discount_value_type': pgettext_lazy(
                'Discount type of the voucher',
                'Discount type'),
            'discount_value': pgettext_lazy(
                'Discount value of the voucher',
                'Discount value')}

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial', {})
        instance = kwargs.get('instance')
        if instance and instance.id is None and not initial.get('code'):
            initial['code'] = self._generate_code
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def _generate_code(self):
        while True:
            code = str(uuid.uuid4()).replace('-', '').upper()[:12]
            if not Voucher.objects.filter(code=code).exists():
                return code


def country_choices():
    country_codes = ShippingMethodCountry.objects.all()
    country_codes = country_codes.values_list('country_code', flat=True)
    country_codes = country_codes.distinct()
    country_dict = dict(COUNTRY_CODE_CHOICES)
    return [
        (country_code, country_dict[country_code])
        for country_code in country_codes]


class ShippingVoucherForm(forms.ModelForm):

    min_amount_spent = MoneyField(
        min_value=ZERO_MONEY, required=False,
        currency=settings.DEFAULT_CURRENCY,
        label=pgettext_lazy(
            'Lowest value for order to be able to use the voucher',
            'Only if order is over or equal to'))
    countries = forms.ChoiceField(
        choices=country_choices,
        required=False,
        label=pgettext_lazy(
            'Text above the dropdown of countries',
            'Countries that free shipping should apply to'))

    class Meta:
        model = Voucher
        fields = ['countries', 'min_amount_spent']

    def save(self, commit=True):
        return super().save(commit)


class ValueVoucherForm(forms.ModelForm):

    min_amount_spent = MoneyField(
        min_value=ZERO_MONEY, required=False,
        currency=settings.DEFAULT_CURRENCY,
        label=pgettext_lazy(
            'Lowest value for order to be able to use the voucher',
            'Only apply if purchase value is greater than or equal to'))

    class Meta:
        model = Voucher
        fields = ['min_amount_spent']

    def save(self, commit=True):
        self.instance.category = None
        self.instance.countries = []
        self.instance.product = None
        return super().save(commit)


class CommonVoucherForm(forms.ModelForm):

    use_required_attribute = False

    def save(self, commit=True):
        self.instance.min_amount_spent = None
        return super().save(commit)


class ProductVoucherForm(CommonVoucherForm):
    products = AjaxSelect2MultipleChoiceField(
        queryset=Product.objects.all(),
        fetch_data_url=reverse_lazy('dashboard:ajax-products'),
        required=True,
        label=pgettext_lazy('Product', 'Products'))

    class Meta:
        model = Voucher
        fields = ['products']


class CollectionVoucherForm(CommonVoucherForm):

    class Meta:
        model = Voucher
        fields = ['collections']
        labels = {
            'collections': pgettext_lazy(
                'Collections',
                'Collections')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['collections'].required = True
