from django import forms
from django.shortcuts import get_object_or_404
from django.utils.translation import pgettext_lazy
from django.utils.text import slugify
from text_unidecode import unidecode

from ...product.models import Category


class CategoryForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.parent_pk = kwargs.pop('parent_pk')
<<<<<<< HEAD
        super().__init__(*args, **kwargs)
        self.fields['is_hidden'].label = pgettext_lazy(
            'Category form field label', 'Hide in site navigation')
=======
        super(CategoryForm, self).__init__(*args, **kwargs)
>>>>>>> Use useful context descriptions for labels
        if self.instance.parent and self.instance.parent.is_hidden:
            self.fields['is_hidden'].widget.attrs['disabled'] = True

    class Meta:
        model = Category
        exclude = ['slug']
        labels = {
            'name': pgettext_lazy(
                'Category name',
                'Name'),
            'description': pgettext_lazy(
                'Category description',
                'Description'),
            'is_hidden': pgettext_lazy(
                'Hide in site navigation',
                'Hide in site navigation'),
            'parent': pgettext_lazy(
                'Category parent',
                'Category parent')}

    def save(self, commit=True):
        self.instance.slug = slugify(unidecode(self.instance.name))
        if self.parent_pk:
            self.instance.parent = get_object_or_404(
                Category, pk=self.parent_pk)
        if self.instance.parent and self.instance.parent.is_hidden:
            self.instance.is_hidden = True
        super().save(commit=commit)
        self.instance.set_is_hidden_descendants(self.cleaned_data['is_hidden'])
        return self.instance
