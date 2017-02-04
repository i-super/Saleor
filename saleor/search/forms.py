from django import forms
from django.utils.translation import pgettext

from .backends import get_search_backend


class SearchForm(forms.Form):
    q = forms.CharField(label=pgettext('Search form label', 'Query'), required=True)

    def search(self, model_or_queryset):
        backend = get_search_backend('default')
        query = self.cleaned_data['q']
        results = backend.search(query, model_or_queryset=model_or_queryset)
        return results
