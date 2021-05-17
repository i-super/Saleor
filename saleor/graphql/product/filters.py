import math
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

import django_filters
import graphene
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Exists, F, FloatField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Cast, Coalesce
from graphene_django.filter import GlobalIDMultipleChoiceFilter

from ...attribute import AttributeInputType
from ...attribute.models import (
    AssignedProductAttribute,
    AssignedVariantAttribute,
    Attribute,
    AttributeValue,
)
from ...product.models import Category, Collection, Product, ProductType, ProductVariant
from ...warehouse.models import Stock
from ..channel.filters import get_channel_slug_from_filter_data
from ..core.filters import (
    EnumFilter,
    ListObjectTypeFilter,
    MetadataFilterBase,
    ObjectTypeFilter,
)
from ..core.types import ChannelFilterInputObjectType, FilterInputObjectType
from ..core.types.common import IntRangeInput, PriceRangeInput
from ..utils import get_nodes, resolve_global_ids_to_primary_keys
from ..utils.filters import filter_fields_containing_value, filter_range_field
from ..warehouse import types as warehouse_types
from .enums import (
    CollectionPublished,
    ProductTypeConfigurable,
    ProductTypeEnum,
    StockAvailability,
)

T_PRODUCT_FILTER_QUERIES = Dict[int, Iterable[int]]


def _clean_product_attributes_filter_input(filter_value, queries):
    attributes = Attribute.objects.prefetch_related("values")
    attributes_map: Dict[str, int] = {
        attribute.slug: attribute.pk for attribute in attributes
    }
    values_map: Dict[str, Dict[str, int]] = {
        attr.slug: {value.slug: value.pk for value in attr.values.all()}
        for attr in attributes
    }

    # Convert attribute:value pairs into a dictionary where
    # attributes are keys and values are grouped in lists
    for attr_name, val_slugs in filter_value:
        if attr_name not in attributes_map:
            raise ValueError("Unknown attribute name: %r" % (attr_name,))
        attr_pk = attributes_map[attr_name]
        attr_val_pk = [
            values_map[attr_name][val_slug]
            for val_slug in val_slugs
            if val_slug in values_map[attr_name]
        ]
        queries[attr_pk] += attr_val_pk


def _clean_product_attributes_range_filter_input(filter_value, queries):
    values = (
        AttributeValue.objects.filter(attribute__input_type=AttributeInputType.NUMERIC)
        .annotate(numeric_value=Cast("name", FloatField()))
        .select_related("attribute")
    )

    attributes_map: Dict[str, int] = {}
    values_map: Dict[str, Dict[str, int]] = defaultdict(dict)
    for value_data in values.values_list(
        "attribute_id", "attribute__slug", "pk", "numeric_value"
    ):
        attr_pk, attr_slug, pk, numeric_value = value_data
        attributes_map[attr_slug] = attr_pk
        values_map[attr_slug][numeric_value] = pk

    for attr_name, val_range in filter_value:
        if attr_name not in attributes_map:
            raise ValueError("Unknown numeric attribute name: %r" % (attr_name,))
        gte, lte = val_range.get("gte", 0), val_range.get("lte", math.inf)
        attr_pk = attributes_map[attr_name]
        attr_values = values_map[attr_name]
        matching_values = [
            value for value in attr_values.keys() if gte <= value and lte >= value
        ]
        attr_val_pks = [attr_values[value] for value in matching_values]
        queries[attr_pk] += attr_val_pks


def filter_products_by_attributes_values(qs, queries: T_PRODUCT_FILTER_QUERIES):
    filters = [
        Q(
            Exists(
                AssignedProductAttribute.objects.filter(
                    product__id=OuterRef("pk"), values__pk__in=values
                )
            )
        )
        | Q(
            Exists(
                AssignedVariantAttribute.objects.filter(
                    variant__product__id=OuterRef("pk"),
                    values__pk__in=values,
                )
            )
        )
        for values in queries.values()
    ]
    return qs.filter(*filters)


def filter_products_by_attributes(qs, filter_values, filter_range_values):
    queries: Dict[int, List[Optional[int]]] = defaultdict(list)
    try:
        if filter_values:
            _clean_product_attributes_filter_input(filter_values, queries)
        if filter_range_values:
            _clean_product_attributes_range_filter_input(filter_range_values, queries)
    except ValueError:
        return Product.objects.none()
    return filter_products_by_attributes_values(qs, queries)


def filter_products_by_variant_price(qs, channel_slug, price_lte=None, price_gte=None):
    if price_lte:
        qs = qs.filter(
            Q(variants__channel_listings__price_amount__lte=price_lte)
            | Q(variants__channel_listings__price_amount__isnull=True),
            variants__channel_listings__channel__slug=channel_slug,
        )
    if price_gte:
        qs = qs.filter(
            Q(variants__channel_listings__price_amount__gte=price_gte)
            | Q(variants__channel_listings__price_amount__isnull=True),
            variants__channel_listings__channel__slug=channel_slug,
        )
    return qs


def filter_products_by_minimal_price(
    qs, channel_slug, minimal_price_lte=None, minimal_price_gte=None
):
    if minimal_price_lte:
        qs = qs.filter(
            channel_listings__discounted_price_amount__lte=minimal_price_lte,
            channel_listings__discounted_price_amount__isnull=False,
            channel_listings__channel__slug=channel_slug,
        )
    if minimal_price_gte:
        qs = qs.filter(
            channel_listings__discounted_price_amount__gte=minimal_price_gte,
            channel_listings__discounted_price_amount__isnull=False,
            channel_listings__channel__slug=channel_slug,
        )
    return qs


def filter_products_by_categories(qs, categories):
    categories = [
        category.get_descendants(include_self=True) for category in categories
    ]
    ids = {category.id for tree in categories for category in tree}
    return qs.filter(category__in=ids)


def filter_products_by_collections(qs, collections):
    return qs.filter(collections__in=collections)


def filter_products_by_stock_availability(qs, stock_availability, channel_slug):
    total_stock = (
        Stock.objects.for_channel(channel_slug)
        .select_related("product_variant")
        .values("product_variant__product_id")
        .annotate(
            total_quantity_allocated=Coalesce(Sum("allocations__quantity_allocated"), 0)
        )
        .annotate(total_quantity=Coalesce(Sum("quantity"), 0))
        .annotate(total_available=F("total_quantity") - F("total_quantity_allocated"))
        .filter(
            total_available__lte=0,
        )
        .values_list("product_variant__product_id", flat=True)
    )
    if stock_availability == StockAvailability.IN_STOCK:
        qs = qs.exclude(id__in=Subquery(total_stock))
    elif stock_availability == StockAvailability.OUT_OF_STOCK:
        qs = qs.filter(id__in=Subquery(total_stock))
    return qs


def _filter_attributes(qs, _, value):
    if value:
        value_list = []
        value_range_list = []
        for v in value:
            slug = v["slug"]
            if "values" in v:
                value_list.append((slug, v["values"]))
            elif "values_range" in v:
                value_range_list.append((slug, v["values_range"]))
        qs = filter_products_by_attributes(qs, value_list, value_range_list)
    return qs


def filter_categories(qs, _, value):
    if value:
        categories = get_nodes(value, "Category", Category)
        qs = filter_products_by_categories(qs, categories)
    return qs


def filter_has_category(qs, _, value):
    return qs.filter(category__isnull=not value)


def filter_collections(qs, _, value):
    if value:
        collections = get_nodes(value, "Collection", Collection)
        qs = filter_products_by_collections(qs, collections)
    return qs


def _filter_is_published(qs, _, value, channel_slug):
    return qs.filter(
        channel_listings__is_published=value,
        channel_listings__channel__slug=channel_slug,
    )


def _filter_variant_price(qs, _, value, channel_slug):
    qs = filter_products_by_variant_price(
        qs, channel_slug, price_lte=value.get("lte"), price_gte=value.get("gte")
    )
    return qs


def _filter_minimal_price(qs, _, value, channel_slug):
    qs = filter_products_by_minimal_price(
        qs,
        channel_slug,
        minimal_price_lte=value.get("lte"),
        minimal_price_gte=value.get("gte"),
    )
    return qs


def _filter_stock_availability(qs, _, value, channel_slug):
    if value:
        qs = filter_products_by_stock_availability(qs, value, channel_slug)
    return qs


def product_search(qs, phrase):
    """Return matching products for storefront views.

        Name and description is matched using search vector.

    Args:
        qs (ProductsQueryset): searched data set
        phrase (str): searched phrase

    """
    query = SearchQuery(phrase, config="english")
    vector = F("search_vector")
    ft_in_description_or_name = Q(search_vector=query)

    variants = ProductVariant.objects.filter(sku=phrase).values("id")
    ft_by_sku = Q(Exists(variants.filter(product_id=OuterRef("pk"))))

    return (
        qs.annotate(rank=SearchRank(vector, query))
        .filter((ft_in_description_or_name | ft_by_sku))
        .order_by("-rank", "id")
    )


def filter_search(qs, _, value):
    if value:
        qs = product_search(qs, value)
    return qs


def filter_product_type_configurable(qs, _, value):
    if value == ProductTypeConfigurable.CONFIGURABLE:
        qs = qs.filter(has_variants=True)
    elif value == ProductTypeConfigurable.SIMPLE:
        qs = qs.filter(has_variants=False)
    return qs


def filter_product_type(qs, _, value):
    if value == ProductTypeEnum.DIGITAL:
        qs = qs.filter(is_digital=True)
    elif value == ProductTypeEnum.SHIPPABLE:
        qs = qs.filter(is_shipping_required=True)
    return qs


def filter_stocks(qs, _, value):
    warehouse_ids = value.get("warehouse_ids")
    quantity = value.get("quantity")
    # distinct's wil be removed in separated PR
    if warehouse_ids and not quantity:
        return filter_warehouses(qs, _, warehouse_ids).distinct()
    if quantity and not warehouse_ids:
        return filter_quantity(qs, quantity).distinct()
    if quantity and warehouse_ids:
        return filter_quantity(qs, quantity, warehouse_ids).distinct()
    return qs


def filter_warehouses(qs, _, value):
    if value:
        _, warehouse_pks = resolve_global_ids_to_primary_keys(
            value, warehouse_types.Warehouse
        )
        return qs.filter(variants__stocks__warehouse__pk__in=warehouse_pks)
    return qs


def filter_sku_list(qs, _, value):
    return qs.filter(sku__in=value)


def filter_quantity(qs, quantity_value, warehouses=None):
    """Filter products queryset by product variants quantity.

    Return product queryset which contains at least one variant with aggregated quantity
    between given range. If warehouses is given, it aggregates quantity only
    from stocks which are in given warehouses.
    """
    product_variants = ProductVariant.objects.filter(product__in=qs)
    if warehouses:
        _, warehouse_pks = resolve_global_ids_to_primary_keys(
            warehouses, warehouse_types.Warehouse
        )
        product_variants = product_variants.annotate(
            total_quantity=Sum(
                "stocks__quantity", filter=Q(stocks__warehouse__pk__in=warehouse_pks)
            )
        )
    else:
        product_variants = product_variants.annotate(
            total_quantity=Sum("stocks__quantity")
        )

    product_variants = filter_range_field(
        product_variants, "total_quantity", quantity_value
    )
    return qs.filter(variants__in=product_variants)


class ProductStockFilterInput(graphene.InputObjectType):
    warehouse_ids = graphene.List(graphene.NonNull(graphene.ID), required=False)
    quantity = graphene.Field(IntRangeInput, required=False)


class ProductFilter(MetadataFilterBase):
    is_published = django_filters.BooleanFilter(method="filter_is_published")
    collections = GlobalIDMultipleChoiceFilter(method=filter_collections)
    categories = GlobalIDMultipleChoiceFilter(method=filter_categories)
    has_category = django_filters.BooleanFilter(method=filter_has_category)
    price = ObjectTypeFilter(input_class=PriceRangeInput, method="filter_variant_price")
    minimal_price = ObjectTypeFilter(
        input_class=PriceRangeInput,
        method="filter_minimal_price",
        field_name="minimal_price_amount",
    )
    attributes = ListObjectTypeFilter(
        input_class="saleor.graphql.attribute.types.AttributeInput",
        method="filter_attributes",
    )
    stock_availability = EnumFilter(
        input_class=StockAvailability, method="filter_stock_availability"
    )
    product_types = GlobalIDMultipleChoiceFilter(field_name="product_type")
    stocks = ObjectTypeFilter(input_class=ProductStockFilterInput, method=filter_stocks)
    search = django_filters.CharFilter(method=filter_search)
    ids = GlobalIDMultipleChoiceFilter(field_name="id")

    class Meta:
        model = Product
        fields = [
            "is_published",
            "collections",
            "categories",
            "has_category",
            "attributes",
            "stock_availability",
            "stocks",
            "search",
        ]

    def filter_attributes(self, queryset, name, value):
        return _filter_attributes(queryset, name, value)

    def filter_variant_price(self, queryset, name, value):
        channel_slug = get_channel_slug_from_filter_data(self.data)
        return _filter_variant_price(queryset, name, value, channel_slug)

    def filter_minimal_price(self, queryset, name, value):
        channel_slug = get_channel_slug_from_filter_data(self.data)
        return _filter_minimal_price(queryset, name, value, channel_slug)

    def filter_is_published(self, queryset, name, value):
        channel_slug = get_channel_slug_from_filter_data(self.data)
        return _filter_is_published(queryset, name, value, channel_slug)

    def filter_stock_availability(self, queryset, name, value):
        channel_slug = get_channel_slug_from_filter_data(self.data)
        return _filter_stock_availability(queryset, name, value, channel_slug)


class ProductVariantFilter(MetadataFilterBase):
    search = django_filters.CharFilter(
        method=filter_fields_containing_value("name", "product__name", "sku")
    )
    sku = ListObjectTypeFilter(input_class=graphene.String, method=filter_sku_list)

    class Meta:
        model = ProductVariant
        fields = ["search", "sku"]


class CollectionFilter(MetadataFilterBase):
    published = EnumFilter(
        input_class=CollectionPublished, method="filter_is_published"
    )
    search = django_filters.CharFilter(
        method=filter_fields_containing_value("slug", "name")
    )
    ids = GlobalIDMultipleChoiceFilter(field_name="id")

    class Meta:
        model = Collection
        fields = ["published", "search"]

    def filter_is_published(self, queryset, name, value):
        channel_slug = get_channel_slug_from_filter_data(self.data)
        if value == CollectionPublished.PUBLISHED:
            return _filter_is_published(queryset, name, True, channel_slug)
        elif value == CollectionPublished.HIDDEN:
            return _filter_is_published(queryset, name, False, channel_slug)
        return queryset


class CategoryFilter(MetadataFilterBase):
    search = django_filters.CharFilter(
        method=filter_fields_containing_value("slug", "name", "description")
    )
    ids = GlobalIDMultipleChoiceFilter(field_name="id")

    class Meta:
        model = Category
        fields = ["search"]


class ProductTypeFilter(MetadataFilterBase):
    search = django_filters.CharFilter(
        method=filter_fields_containing_value("name", "slug")
    )

    configurable = EnumFilter(
        input_class=ProductTypeConfigurable, method=filter_product_type_configurable
    )

    product_type = EnumFilter(input_class=ProductTypeEnum, method=filter_product_type)
    ids = GlobalIDMultipleChoiceFilter(field_name="id")

    class Meta:
        model = ProductType
        fields = ["search", "configurable", "product_type"]


class ProductFilterInput(ChannelFilterInputObjectType):
    class Meta:
        filterset_class = ProductFilter


class ProductVariantFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = ProductVariantFilter


class CollectionFilterInput(ChannelFilterInputObjectType):
    class Meta:
        filterset_class = CollectionFilter


class CategoryFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = CategoryFilter


class ProductTypeFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = ProductTypeFilter
