import django_filters
import graphene
from django.db.models import Exists, OuterRef
from graphene_django.filter import GlobalIDMultipleChoiceFilter
from graphql.error import GraphQLError

from ...account import models as account_models
from ...giftcard import models
from ...product import models as product_models
from ..account import types as account_types
from ..core.filters import ListObjectTypeFilter, MetadataFilterBase, ObjectTypeFilter
from ..core.types import FilterInputObjectType
from ..core.types.common import PriceRangeInput
from ..product.types import products as product_types
from ..utils import resolve_global_ids_to_primary_keys


def filter_gift_card_tag(qs, _, value):
    if not value:
        return qs
    return qs.filter(tag__ilike=value)


def filter_products(qs, _, value):
    if value:
        _, product_pks = resolve_global_ids_to_primary_keys(
            value, product_types.Product
        )
        qs = filter_gift_cards_by_products(qs, product_pks)
    return qs


def filter_gift_cards_by_products(qs, product_ids):
    products = product_models.Product.objects.filter(pk__in=product_ids)
    return qs.filter(Exists(products.filter(pk=OuterRef("product_id"))))


def filter_used_by(qs, _, value):
    if value:
        _, user_pks = resolve_global_ids_to_primary_keys(value, account_types.User)
        qs = filter_gift_cards_by_used_by_user(qs, user_pks)
    return qs


def filter_gift_cards_by_used_by_user(qs, user_pks):
    users = account_models.User.objects.filter(pk__in=user_pks)
    return qs.filter(Exists(users.filter(pk=OuterRef("used_by_id"))))


def filter_tags_list(qs, _, value):
    if not value:
        return qs
    return qs.filter(tag__in=value)


def filter_currency(qs, _, value):
    if not value:
        return qs
    return qs.filter(currency=value)


def _filter_by_price(qs, field, value):
    lookup = {}
    if lte := value.get("lte"):
        lookup[f"{field}_amount__lte"] = lte
    if gte := value.get("gte"):
        lookup[f"{field}_amount__gte"] = gte
    return qs.filter(**lookup)


def filter_code(qs, _, value):
    if not value:
        return qs
    return qs.filter(code=value)


class GiftCardFilter(MetadataFilterBase):
    tag = django_filters.CharFilter(method=filter_gift_card_tag)
    tags = ListObjectTypeFilter(input_class=graphene.String, method=filter_tags_list)
    products = GlobalIDMultipleChoiceFilter(method=filter_products)
    used_by = GlobalIDMultipleChoiceFilter(method=filter_used_by)
    currency = django_filters.CharFilter(method=filter_currency)
    current_balance = ObjectTypeFilter(
        input_class=PriceRangeInput, method="filter_current_balance"
    )
    initial_balance = ObjectTypeFilter(
        input_class=PriceRangeInput, method="filter_initial_balance"
    )
    is_active = django_filters.BooleanFilter()
    code = django_filters.CharFilter(method=filter_code)

    class Meta:
        model = models.GiftCard
        fields = ["is_active"]

    def filter_current_balance(self, queryset, name, value):
        check_currency_in_filter_data(self.data)
        return _filter_by_price(queryset, "current_balance", value)

    def filter_initial_balance(self, queryset, name, value):
        check_currency_in_filter_data(self.data)
        return _filter_by_price(queryset, "initial_balance", value)


def check_currency_in_filter_data(filter_data: dict):
    currency = filter_data.get("currency")
    if not currency:
        raise GraphQLError(
            "You must provide a `currency` filter parameter for filtering by price."
        )


class GiftCardFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = GiftCardFilter
