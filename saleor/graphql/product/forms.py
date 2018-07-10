from django import forms

from ...product.models import Product, ProductVariant


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        exclude = ['updated_at']


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        exclude = ['images', 'name', 'product', 'quantity_allocated']
