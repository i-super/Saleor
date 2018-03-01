import graphene
from django.db.models import Q
from graphene import relay
from graphene_django.filter import DjangoFilterConnectionField

from ...product import models
from ...product.templatetags.product_images import product_first_image
from ...product.utils import get_availability
from ..core.filters import DistinctFilterSet
from ..core.types import CountableDjangoObjectType, Price, PriceRange
from ..utils import get_node
from .filters import ProductFilterSet


class ProductAvailability(graphene.ObjectType):
    available = graphene.Boolean()
    on_sale = graphene.Boolean()
    discount = graphene.Field(Price)
    discount_local_currency = graphene.Field(Price)
    price_range = graphene.Field(PriceRange)
    price_range_undiscounted = graphene.Field(PriceRange)
    price_range_local_currency = graphene.Field(PriceRange)


class Product(CountableDjangoObjectType):
    url = graphene.String()
    thumbnail_url = graphene.String(
        size=graphene.Argument(
            graphene.String,
            description='The size of a thumbnail, for example 255x255'))
    images = graphene.List(lambda: ProductImage)
    variants = graphene.List(lambda: ProductVariant)
    availability = graphene.Field(ProductAvailability)
    price = graphene.Field(Price)

    class Meta:
        model = models.Product
        interfaces = [relay.Node]

    def resolve_thumbnail_url(self, info, *, size=None):
        if not size:
            size = '255x255'
        return product_first_image(self, size)

    def resolve_images(self, info):
        return self.images.all()

    def resolve_variants(self, info):
        return self.variants.all()

    def resolve_url(self, info):
        return self.get_absolute_url()

    def resolve_availability(self, info):
        context = info.context
        availability = get_availability(
            self, context.discounts, context.currency)
        return ProductAvailability(**availability._asdict())


class Category(CountableDjangoObjectType):
    products = DjangoFilterConnectionField(
        Product, filterset_class=ProductFilterSet,
        sort_by=graphene.Argument(graphene.String))
    url = graphene.String()
    ancestors = DjangoFilterConnectionField(
        lambda: Category, filterset_class=DistinctFilterSet)
    children = DjangoFilterConnectionField(
        lambda: Category, filterset_class=DistinctFilterSet)
    siblings = DjangoFilterConnectionField(
        lambda: Category, filterset_class=DistinctFilterSet)

    class Meta:
        model = models.Category
        filter_fields = ['id', 'name']
        interfaces = [relay.Node]

    def resolve_ancestors(self, info, **kwargs):
        return self.get_ancestors().distinct()

    def resolve_children(self, info, **kwargs):
        return self.children.distinct()

    def resolve_siblings(self, info, **kwargs):
        return self.get_siblings().distinct()

    def resolve_url(self, info):
        ancestors = self.get_ancestors().distinct()
        return self.get_absolute_url(ancestors)

    def resolve_products(self, info, sort_by=None, **kwargs):
        qs = models.Product.objects.available_products()
        qs = qs.filter(category=self)
        if sort_by == 'name':
            qs = qs.order_by('name')
        return qs.distinct()


class ProductVariant(CountableDjangoObjectType):
    stock_quantity = graphene.Int()
    price_override = graphene.Field(Price)

    class Meta:
        model = models.ProductVariant
        interfaces = [relay.Node]

    def resolve_stock_quantity(self, info):
        return self.get_stock_quantity()


class ProductImage(CountableDjangoObjectType):
    url = graphene.String(size=graphene.String())

    class Meta:
        model = models.ProductImage
        interfaces = [relay.Node]

    def resolve_url(self, info, *, size=None):
        if size:
            return self.image.crop[size].url
        return self.image.url


class ProductAttributeValue(CountableDjangoObjectType):
    class Meta:
        model = models.AttributeChoiceValue
        interfaces = [relay.Node]


class ProductAttribute(CountableDjangoObjectType):
    values = graphene.List(ProductAttributeValue)

    class Meta:
        model = models.ProductAttribute
        filter_fields = ['id', 'slug']
        interfaces = [relay.Node]

    def resolve_values(self, info):
        return self.values.all()


def resolve_categories(info, level=None):
    qs = models.Category.objects.all()
    if level is not None:
        qs = qs.filter(level=level)
    return qs.distinct()


def resolve_products(info):
    return models.Product.objects.available_products().distinct()


def resolve_attributes(category_id, info):
    queryset = models.ProductAttribute.objects.prefetch_related('values')
    if category_id:
        # Get attributes that are used with product types
        # within the given category.
        category = get_node(info, category_id, only_type=Category)
        if category is None:
            return queryset.none()
        tree = category.get_descendants(include_self=True)
        product_types = {
            obj[0]
            for obj in models.Product.objects.filter(
                category__in=tree).values_list('product_type_id')}
        queryset = queryset.filter(
            Q(product_types__in=product_types)
            | Q(product_variant_types__in=product_types))
    return queryset.distinct()
