import django_filters
from graphene_django.filter import GlobalIDMultipleChoiceFilter

from ...page.models import Page
from ..core.filters import MetadataFilterBase
from ..core.types import FilterInputObjectType
from ..utils.filters import filter_by_query_param


def filter_page_search(qs, _, value):
    page_fields = ["content", "slug", "title"]
    qs = filter_by_query_param(qs, value, page_fields)
    return qs


def filter_page_type_search(qs, _, value):
    fields = ["name", "slug"]
    if value:
        qs = filter_by_query_param(qs, value, fields)
    return qs


class PageFilter(MetadataFilterBase):
    search = django_filters.CharFilter(method=filter_page_search)
    page_types = GlobalIDMultipleChoiceFilter(field_name="page_type")

    class Meta:
        model = Page
        fields = ["search"]


class PageFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = PageFilter


class PageTypeFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method=filter_page_type_search)


class PageTypeFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = PageTypeFilter
