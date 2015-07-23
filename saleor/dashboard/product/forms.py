from __future__ import unicode_literals

from django import forms
from django.forms.models import inlineformset_factory
from django.utils.translation import pgettext_lazy

from ...product.models import (ProductImage, Stock, ProductVariant, Product,
                               ProductAttribute, AttributeChoiceValue)
from .widgets import ImagePreviewWidget

PRODUCT_CLASSES = {Product: 'Default'}


class ProductClassForm(forms.Form):
    product_cls = forms.ChoiceField(
        label=pgettext_lazy('Product class form label', 'Product class'),
        widget=forms.RadioSelect,
        choices=[(cls.__name__, presentation) for cls, presentation in
                 PRODUCT_CLASSES.items()])

    def __init__(self, *args, **kwargs):
        super(ProductClassForm, self).__init__(*args, **kwargs)
        product_class = next(iter((PRODUCT_CLASSES)))
        self.fields['product_cls'].initial = product_class.__name__


class StockForm(forms.ModelForm):
    class Meta:
        model = Stock
        exclude = []

    def __init__(self, *args, **kwargs):
        product = kwargs.pop('product')
        super(StockForm, self).__init__(*args, **kwargs)
        self.fields['variant'] = forms.ModelChoiceField(
            queryset=product.variants)


class ProductForm(forms.ModelForm):
    available_on_submit = forms.DateField(widget=forms.HiddenInput(),
                                          input_formats=['%Y/%m/%d'],
                                          required=False)

    class Meta:
        model = Product
        exclude = []

    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        self.fields['name'].widget.attrs['placeholder'] = pgettext_lazy(
            'Product form labels', 'Give your awesome product a name')
        self.fields['categories'].widget.attrs[
            'data-placeholder'] = pgettext_lazy('Product form labels', 'Search')
        self.fields['attributes'].widget.attrs[
            'data-placeholder'] = pgettext_lazy('Product form labels', 'Search')
        if self.instance.available_on:
            self.fields['available_on'].widget.attrs[
                'datavalue'] = self.instance.available_on.strftime('%Y/%m/%d')

    def clean(self):
        data = super(ProductForm, self).clean()
        data['available_on'] = data.get('available_on_submit')
        if data['available_on'] and 'available_on' in self._errors:
            del self._errors['available_on']
        return data


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        exclude = ['attributes', 'product']

    def __init__(self, *args, **kwargs):
        super(ProductVariantForm, self).__init__(*args, **kwargs)
        self.fields['price_override'].widget.attrs[
            'placeholder'] = self.instance.product.price.gross
        self.fields['weight_override'].widget.attrs[
            'placeholder'] = self.instance.product.weight


class VariantAttributeForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = []

    def __init__(self, *args, **kwargs):
        super(VariantAttributeForm, self).__init__(*args, **kwargs)
        self.available_attrs = self.instance.product.attributes.prefetch_related(
            'values')
        for attr in self.available_attrs:
            field_defaults = {'label': attr.display,
                              'required': True,
                              'initial': self.instance.get_attribute(attr.pk)}
            if attr.has_values():
                field = forms.ModelChoiceField(queryset=attr.values.all(),
                                               **field_defaults)
            else:
                field = forms.CharField(**field_defaults)
            self.fields[attr.get_formfield_name()] = field

    def save(self, commit=True):
        attributes = {}
        for attr in self.available_attrs:
            value = self.cleaned_data.pop(attr.get_formfield_name())
            attributes[attr.pk] = value.pk if hasattr(value, 'pk') else value
        self.instance.attributes = attributes
        return super(VariantAttributeForm, self).save(commit=commit)


class VariantBulkDeleteForm(forms.Form):
    items = forms.ModelMultipleChoiceField(queryset=ProductVariant.objects)

    def delete(self):
        items = ProductVariant.objects.filter(pk__in=self.cleaned_data['items'])
        items.delete()


class StockBulkDeleteForm(forms.Form):
    items = forms.ModelMultipleChoiceField(queryset=Stock.objects)

    def delete(self):
        items = Stock.objects.filter(pk__in=self.cleaned_data['items'])
        items.delete()


class ProductImageForm(forms.ModelForm):

    class Meta:
        model = ProductImage
        exclude = ('product', 'order')

    def __init__(self, *args, **kwargs):
        super(ProductImageForm, self).__init__(*args, **kwargs)
        if self.instance.image:
            self.fields['image'].widget = ImagePreviewWidget()


class ProductAttributeForm(forms.ModelForm):
    class Meta:
        model = ProductAttribute
        exclude = []


AttributeChoiceValueFormset = inlineformset_factory(
    ProductAttribute, AttributeChoiceValue, exclude=(), extra=1)
