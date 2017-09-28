from __future__ import unicode_literals

from django import forms
from django.db.models import Count
from django.forms.models import ModelChoiceIterator, inlineformset_factory
from django.forms.widgets import CheckboxSelectMultiple
from django.utils.encoding import smart_text
from django.utils.text import slugify
from django.utils.translation import pgettext_lazy

from ...product.models import (
    AttributeChoiceValue, Product, ProductAttribute, ProductClass,
    ProductImage, ProductVariant, Stock, StockLocation, VariantImage)
from ...search import index as search_index
from .widgets import ImagePreviewWidget


class ProductClassSelectorForm(forms.Form):

    def __init__(self, *args, **kwargs):
        product_classes = kwargs.pop('product_classes', [])
        super(ProductClassSelectorForm, self).__init__(*args, **kwargs)
        choices = [(obj.pk, obj.name) for obj in product_classes]
        self.fields['product_cls'] = forms.ChoiceField(
            label=pgettext_lazy('Product class form label', 'Product type'),
            choices=choices, widget=forms.RadioSelect)


class StockForm(forms.ModelForm):
    class Meta:
        model = Stock
        exclude = ['quantity_allocated', 'variant']

    def __init__(self, *args, **kwargs):
        self.variant = kwargs.pop('variant')
        super(StockForm, self).__init__(*args, **kwargs)

    def clean_location(self):
        location = self.cleaned_data['location']
        if (
            not self.instance.pk and
                self.variant.stock.filter(location=location).exists()):
            self.add_error(
                'location',
                pgettext_lazy(
                    'stock form error',
                    'Stock item for this location and variant already exists'))
        return location

    def save(self, commit=True):
        self.instance.variant = self.variant
        return super(StockForm, self).save(commit)


class ProductClassForm(forms.ModelForm):
    class Meta:
        model = ProductClass
        exclude = []
        labels = {
            'variant_attributes': pgettext_lazy(
                'Product class form label',
                'Attributes specific to each variant'),
            'product_attributes': pgettext_lazy(
                'Product class form label',
                'Attributes common to all variants')}

    def clean(self):
        data = super(ProductClassForm, self).clean()
        has_variants = self.cleaned_data['has_variants']
        product_attr = set(self.cleaned_data['product_attributes'])
        variant_attr = set(self.cleaned_data['variant_attributes'])
        if not has_variants and len(variant_attr) > 0:
            msg = pgettext_lazy(
                'Product class form error',
                'Product variants are disabled.')
            self.add_error('variant_attributes', msg)
        if len(product_attr & variant_attr) > 0:
            msg = pgettext_lazy(
                'Product class form error',
                'A single attribute can\'t belong to both a product '
                'and its variant.')
            self.add_error('variant_attributes', msg)

        if self.instance.pk:
            variants_changed = not (self.fields['has_variants'].initial ==
                                    has_variants)
            if variants_changed:
                query = self.instance.products.all()
                query = query.annotate(variants_counter=Count('variants'))
                query = query.filter(variants_counter__gt=1)
                if query.exists():
                    msg = pgettext_lazy(
                        'Product class form error',
                        'Some products of this type have more than '
                        'one variant.')
                    self.add_error('has_variants', msg)
        return data


class ProductForm(forms.ModelForm):

    class Meta:
        model = Product
        exclude = ['attributes', 'product_class']
        labels = {
            'is_published': pgettext_lazy('product form', 'Published'),
            'is_featured': pgettext_lazy(
                'product form', 'Feature this product on homepage')}

    def __init__(self, *args, **kwargs):
        self.product_attributes = []
        super(ProductForm, self).__init__(*args, **kwargs)
        self.fields['categories'].widget.attrs['data-placeholder'] = (
            pgettext_lazy('Product form placeholder', 'Search'))
        product_class = self.instance.product_class
        self.product_attributes = product_class.product_attributes.all()
        self.product_attributes = self.product_attributes.prefetch_related(
            'values')
        self.prepare_fields_for_attributes()

    def prepare_fields_for_attributes(self):
        for attribute in self.product_attributes:
            field_defaults = {
                'label': attribute.name,
                'required': False,
                'initial': self.instance.get_attribute(attribute.pk)}
            if attribute.has_values():
                field = CachingModelChoiceField(
                    queryset=attribute.values.all(), **field_defaults)
            else:
                field = forms.CharField(**field_defaults)
            self.fields[attribute.get_formfield_name()] = field

    def iter_attribute_fields(self):
        for attr in self.product_attributes:
            yield self[attr.get_formfield_name()]

    def save(self, commit=True):
        attributes = {}
        for attr in self.product_attributes:
            value = self.cleaned_data.pop(attr.get_formfield_name())
            if isinstance(value, AttributeChoiceValue):
                attributes[smart_text(attr.pk)] = smart_text(value.pk)
            else:
                attributes[smart_text(attr.pk)] = value
        self.instance.attributes = attributes
        instance = super(ProductForm, self).save(commit=commit)
        search_index.insert_or_update_object(instance)
        return instance


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        exclude = ['attributes', 'product', 'images']

    def __init__(self, *args, **kwargs):
        super(ProductVariantForm, self).__init__(*args, **kwargs)
        if self.instance.product.pk:
            self.fields['price_override'].widget.attrs[
                'placeholder'] = self.instance.product.price.gross


class CachingModelChoiceIterator(ModelChoiceIterator):
    def __iter__(self):
        if self.field.empty_label is not None:
            yield ('', self.field.empty_label)
        for obj in self.queryset:
            yield self.choice(obj)


class CachingModelChoiceField(forms.ModelChoiceField):
    def _get_choices(self):
        if hasattr(self, '_choices'):
            return self._choices
        return CachingModelChoiceIterator(self)
    choices = property(_get_choices, forms.ChoiceField._set_choices)


class VariantAttributeForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = []

    def __init__(self, *args, **kwargs):
        super(VariantAttributeForm, self).__init__(*args, **kwargs)
        attrs = self.instance.product.product_class.variant_attributes.all()
        self.available_attrs = attrs.prefetch_related('values')
        for attr in self.available_attrs:
            field_defaults = {
                'label': attr.name,
                'required': True,
                'initial': self.instance.get_attribute(attr.pk)}
            if attr.has_values():
                field = CachingModelChoiceField(
                    queryset=attr.values.all(), **field_defaults)
            else:
                field = forms.CharField(**field_defaults)
            self.fields[attr.get_formfield_name()] = field

    def save(self, commit=True):
        attributes = {}
        for attr in self.available_attrs:
            value = self.cleaned_data.pop(attr.get_formfield_name())
            if isinstance(value, AttributeChoiceValue):
                attributes[smart_text(attr.pk)] = smart_text(value.pk)
            else:
                attributes[smart_text(attr.pk)] = value
        self.instance.attributes = attributes
        return super(VariantAttributeForm, self).save(commit=commit)


class VariantBulkDeleteForm(forms.Form):
    items = forms.ModelMultipleChoiceField(queryset=ProductVariant.objects)

    def delete(self):
        items = ProductVariant.objects.filter(
            pk__in=self.cleaned_data['items'])
        items.delete()


class StockBulkDeleteForm(forms.Form):
    items = forms.ModelMultipleChoiceField(queryset=Stock.objects)

    def delete(self):
        items = Stock.objects.filter(pk__in=self.cleaned_data['items'])
        items.delete()


class ProductImageForm(forms.ModelForm):
    use_required_attribute = False
    variants = forms.ModelMultipleChoiceField(
        queryset=ProductVariant.objects.none(),
        widget=forms.CheckboxSelectMultiple, required=False)

    class Meta:
        model = ProductImage
        exclude = ('product', 'order')

    def __init__(self, *args, **kwargs):
        super(ProductImageForm, self).__init__(*args, **kwargs)
        if self.instance.image:
            self.fields['image'].widget = ImagePreviewWidget()


class VariantImagesSelectForm(forms.Form):
    images = forms.ModelMultipleChoiceField(
        queryset=VariantImage.objects.none(),
        widget=CheckboxSelectMultiple,
        required=False)

    def __init__(self, *args, **kwargs):
        self.variant = kwargs.pop('variant')
        super(VariantImagesSelectForm, self).__init__(*args, **kwargs)
        self.fields['images'].queryset = self.variant.product.images.all()
        self.fields['images'].initial = self.variant.images.all()

    def save(self):
        images = []
        self.variant.images.clear()
        for image in self.cleaned_data['images']:
            images.append(VariantImage(variant=self.variant, image=image))
        VariantImage.objects.bulk_create(images)


class ProductAttributeForm(forms.ModelForm):
    class Meta:
        model = ProductAttribute
        exclude = []


class StockLocationForm(forms.ModelForm):
    class Meta:
        model = StockLocation
        exclude = []


class AttributeChoiceValueForm(forms.ModelForm):
    class Meta:
        model = AttributeChoiceValue
        exclude = ('slug', )

    def save(self, commit=True):
        self.instance.slug = slugify(self.instance.name)
        return super(AttributeChoiceValueForm, self).save(commit=commit)


AttributeChoiceValueFormset = inlineformset_factory(
    ProductAttribute, AttributeChoiceValue, form=AttributeChoiceValueForm,
    extra=1)


class OrderedModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    def clean(self, value):
        qs = super(OrderedModelMultipleChoiceField, self).clean(value)
        keys = list(map(int, value))
        return sorted(qs, key=lambda v: keys.index(v.pk))


class ReorderProductImagesForm(forms.ModelForm):
    ordered_images = OrderedModelMultipleChoiceField(
        queryset=ProductImage.objects.none())

    class Meta:
        model = Product
        fields = ()

    def __init__(self, *args, **kwargs):
        super(ReorderProductImagesForm, self).__init__(*args, **kwargs)
        if self.instance:
            self.fields['ordered_images'].queryset = self.instance.images.all()

    def save(self):
        for order, image in enumerate(self.cleaned_data['ordered_images']):
            image.order = order
            image.save()
        return self.instance


class UploadImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ('image', )

    def __init__(self, *args, **kwargs):
        product = kwargs.pop('product')
        super(UploadImageForm, self).__init__(*args, **kwargs)
        self.instance.product = product
