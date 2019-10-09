from typing import List, Union

import graphene
import graphene_django_optimizer as gql_optimizer
from django.conf import settings
from django.db.models import Prefetch
from graphene import relay
from graphql.error import GraphQLError

from ....product import models
from ....product.templatetags.product_images import (
    get_product_image_thumbnail,
    get_thumbnail,
)
from ....product.utils import calculate_revenue_for_variant
from ....product.utils.availability import (
    get_product_availability,
    get_variant_availability,
)
from ....product.utils.costs import get_margin_for_variant, get_product_costs_data
from ...core.connection import CountableDjangoObjectType
from ...core.enums import ReportingPeriod, TaxRateType
from ...core.fields import FilterInputConnectionField, PrefetchingConnectionField
from ...core.resolvers import resolve_meta, resolve_private_meta
from ...core.types import (
    Image,
    MetadataObjectType,
    Money,
    MoneyRange,
    TaxedMoney,
    TaxedMoneyRange,
    TaxType,
)
from ...decorators import permission_required
from ...translations.enums import LanguageCodeEnum
from ...translations.resolvers import resolve_translation
from ...translations.types import (
    CategoryTranslation,
    CollectionTranslation,
    ProductTranslation,
    ProductVariantTranslation,
)
from ...utils import get_database_id, reporting_period_to_date
from ..enums import OrderDirection, ProductOrderField
from ..filters import AttributeFilterInput
from ..resolvers import resolve_attributes
from .attributes import Attribute, SelectedAttribute
from .digital_contents import DigitalContent


def prefetch_products(info, *_args, **_kwargs):
    """Prefetch products visible to the current user.

    Can be used with models that have the `products` relationship. The queryset
    of products being prefetched is filtered based on permissions of the
    requesting user, to restrict access to unpublished products from non-staff
    users.
    """
    user = info.context.user
    qs = models.Product.objects.visible_to_user(user)
    return Prefetch(
        "products",
        queryset=gql_optimizer.query(qs, info),
        to_attr="prefetched_products",
    )


def prefetch_products_collection_sorted(info, *_args, **_kwargs):
    user = info.context.user
    qs = models.Product.objects.collection_sorted(user)
    return Prefetch(
        "products",
        queryset=gql_optimizer.query(qs, info),
        to_attr="prefetched_products",
    )


def resolve_attribute_list(
    instance: Union[models.Product, models.ProductVariant], *, user
) -> List[SelectedAttribute]:
    """Resolve attributes from a product into a list of `SelectedAttribute`s.

    Note: you have to prefetch the below M2M fields.
        - product_type -> attribute[rel] -> [rel]assignments -> values
        - product_type -> attribute[rel] -> attribute
    """
    resolved_attributes = []

    # Retrieve the product type
    if isinstance(instance, models.Product):
        product_type = instance.product_type
        product_type_attributes_assoc_field = "attributeproduct"
        assigned_attribute_instance_field = "productassignments"
        assigned_attribute_instance_filters = {"product_id": instance.pk}
    elif isinstance(instance, models.ProductVariant):
        product_type = instance.product.product_type
        product_type_attributes_assoc_field = "attributevariant"
        assigned_attribute_instance_field = "variantassignments"
        assigned_attribute_instance_filters = {"variant_id": instance.pk}
    else:
        raise AssertionError(f"{instance.__class__.__name__} is unsupported")

    # Retrieve all the product attributes assigned to this product type
    attributes_qs = getattr(product_type, product_type_attributes_assoc_field)
    attributes_qs = attributes_qs.get_visible_to_user(user)

    # An empty QuerySet for unresolved values
    empty_qs = models.AttributeValue.objects.none()

    # Goes through all the attributes assigned to the product type
    # The assigned values are returned as a QuerySet, but will assign a
    # dummy empty QuerySet if no values are assigned to the given instance.
    for attr_data_rel in attributes_qs:
        attr_instance_data = getattr(attr_data_rel, assigned_attribute_instance_field)

        # Retrieve the instance's associated data
        attr_data = attr_instance_data.filter(**assigned_attribute_instance_filters)
        attr_data = attr_data.first()

        # Return the instance's attribute values if the assignment was found,
        # otherwise it sets the values as an empty QuerySet
        values = attr_data.values.all() if attr_data is not None else empty_qs
        resolved_attributes.append(
            SelectedAttribute(attribute=attr_data_rel.attribute, values=values)
        )
    return resolved_attributes


class ProductOrder(graphene.InputObjectType):
    field = graphene.Argument(
        ProductOrderField, description="Sort products by the selected field."
    )
    attribute_id = graphene.Argument(
        graphene.ID,
        description=(
            "Sort product by the selected attribute's values.\n"
            "Note: this doesn't take translations into account yet."
        ),
    )
    direction = graphene.Argument(
        OrderDirection,
        required=True,
        description="Specifies the direction in which to sort products.",
    )


class Margin(graphene.ObjectType):
    start = graphene.Int()
    stop = graphene.Int()


class BasePricingInfo(graphene.ObjectType):
    available = graphene.Boolean(
        description="Whether it is in stock and visible or not.",
        deprecation_reason=(
            "DEPRECATED: Will be removed in Saleor 2.10, "
            "this has been moved to the parent type as 'isAvailable'."
        ),
    )
    on_sale = graphene.Boolean(description="Whether it is in sale or not.")
    discount = graphene.Field(
        TaxedMoney, description="The discount amount if in sale (null otherwise)."
    )
    discount_local_currency = graphene.Field(
        TaxedMoney, description="The discount amount in the local currency."
    )


class VariantPricingInfo(BasePricingInfo):
    discount_local_currency = graphene.Field(
        TaxedMoney, description="The discount amount in the local currency."
    )
    price = graphene.Field(
        TaxedMoney, description="The price, with any discount subtracted."
    )
    price_undiscounted = graphene.Field(
        TaxedMoney, description="The price without any discount."
    )
    price_local_currency = graphene.Field(
        TaxedMoney, description="The discounted price in the local currency."
    )

    class Meta:
        description = "Represents availability of a variant in the storefront."


class ProductPricingInfo(BasePricingInfo):
    price_range = graphene.Field(
        TaxedMoneyRange,
        description="The discounted price range of the product variants.",
    )
    price_range_undiscounted = graphene.Field(
        TaxedMoneyRange,
        description="The undiscounted price range of the product variants.",
    )
    price_range_local_currency = graphene.Field(
        TaxedMoneyRange,
        description=(
            "The discounted price range of the product variants "
            "in the local currency."
        ),
    )

    class Meta:
        description = "Represents availability of a product in the storefront."


class ProductVariant(CountableDjangoObjectType, MetadataObjectType):
    quantity = graphene.Int(
        required=True,
        description="Quantity of a product in the store's possession, "
        "including the allocated stock that is waiting for shipment.",
    )
    stock_quantity = graphene.Int(
        required=True, description="Quantity of a product available for sale."
    )
    price_override = graphene.Field(
        Money,
        description=(
            "Override the base price of a product if necessary. A value of `null` "
            "indicates that the default product price is used."
        ),
    )
    price = graphene.Field(
        Money,
        description="Price of the product variant.",
        deprecation_reason=(
            "DEPRECATED: Will be removed in Saleor 2.10, "
            "has been replaced by 'pricing.priceUndiscounted'"
        ),
    )
    availability = graphene.Field(
        VariantPricingInfo,
        description=(
            "Informs about variant's availability in the storefront, current price and "
            "discounted price."
        ),
        deprecation_reason=(
            "DEPRECATED: Will be removed in Saleor 2.10, has been renamed to `pricing`."
        ),
    )
    pricing = graphene.Field(
        VariantPricingInfo,
        description=(
            "Lists the storefront variant's pricing, the current price and discounts, "
            "only meant for displaying."
        ),
    )
    is_available = graphene.Boolean(
        description="Whether the variant is in stock and visible or not."
    )
    attributes = gql_optimizer.field(
        graphene.List(
            graphene.NonNull(SelectedAttribute),
            required=True,
            description="List of attributes assigned to this variant.",
        )
    )
    cost_price = graphene.Field(Money, description="Cost price of the variant.")
    margin = graphene.Int(description="Gross margin percentage value.")
    quantity_ordered = graphene.Int(description="Total quantity ordered.")
    revenue = graphene.Field(
        TaxedMoney,
        period=graphene.Argument(ReportingPeriod),
        description=(
            "Total revenue generated by a variant in given period of time. Note: this "
            "field should be queried using `reportProductSales` query as it uses "
            "optimizations suitable for such calculations."
        ),
    )
    images = gql_optimizer.field(
        graphene.List(
            lambda: ProductImage, description="List of images for the product variant."
        ),
        model_field="images",
    )
    translation = graphene.Field(
        ProductVariantTranslation,
        language_code=graphene.Argument(
            LanguageCodeEnum,
            description="A language code to return the translation for.",
            required=True,
        ),
        description=(
            "Returns translated Product Variant fields " "for the given language code."
        ),
        resolver=resolve_translation,
    )
    digital_content = gql_optimizer.field(
        graphene.Field(
            DigitalContent, description="Digital content for the product variant."
        ),
        model_field="digital_content",
    )

    class Meta:
        description = (
            "Represents a version of a product such as different size or color."
        )
        only_fields = [
            "id",
            "name",
            "product",
            "quantity_allocated",
            "sku",
            "track_inventory",
            "weight",
        ]
        interfaces = [relay.Node]
        model = models.ProductVariant

    @staticmethod
    @permission_required("product.manage_products")
    def resolve_digital_content(root: models.ProductVariant, *_args):
        return getattr(root, "digital_content", None)

    @staticmethod
    def resolve_stock_quantity(root: models.ProductVariant, _info):
        exact_quantity_available = root.quantity_available
        return min(exact_quantity_available, settings.MAX_CHECKOUT_LINE_QUANTITY)

    @staticmethod
    @gql_optimizer.resolver_hints(
        prefetch_related=["attributes__values", "attributes__assignment__attribute"]
    )
    def resolve_attributes(root: models.ProductVariant, info):
        return resolve_attribute_list(root, user=info.context.user)

    @staticmethod
    @permission_required("product.manage_products")
    def resolve_margin(root: models.ProductVariant, *_args):
        return get_margin_for_variant(root)

    @staticmethod
    @permission_required("product.manage_products")
    def resolve_cost_price(root: models.ProductVariant, *_args):
        return root.cost_price

    @staticmethod
    def resolve_price(root: models.ProductVariant, *_args):
        return (
            root.price_override
            if root.price_override is not None
            else root.product.price
        )

    @staticmethod
    @gql_optimizer.resolver_hints(
        prefetch_related=("product",), only=["price_override_amount", "currency"]
    )
    def resolve_pricing(root: models.ProductVariant, info):
        context = info.context
        availability = get_variant_availability(
            root,
            context.discounts,
            context.country,
            context.currency,
            extensions=context.extensions,
        )
        return VariantPricingInfo(**availability._asdict())

    resolve_availability = resolve_pricing

    @staticmethod
    def resolve_is_available(root: models.ProductVariant, _info):
        return root.is_available

    @staticmethod
    @permission_required("product.manage_products")
    def resolve_price_override(root: models.ProductVariant, *_args):
        return root.price_override

    @staticmethod
    @permission_required("product.manage_products")
    def resolve_quantity(root: models.ProductVariant, *_args):
        return root.quantity

    @staticmethod
    @permission_required(["order.manage_orders", "product.manage_products"])
    def resolve_quantity_ordered(root: models.ProductVariant, *_args):
        # This field is added through annotation when using the
        # `resolve_report_product_sales` resolver.
        return getattr(root, "quantity_ordered", None)

    @staticmethod
    @permission_required(["order.manage_orders", "product.manage_products"])
    def resolve_quantity_allocated(root: models.ProductVariant, *_args):
        return root.quantity_allocated

    @staticmethod
    @permission_required(["order.manage_orders", "product.manage_products"])
    def resolve_revenue(root: models.ProductVariant, *_args, period):
        start_date = reporting_period_to_date(period)
        return calculate_revenue_for_variant(root, start_date)

    @staticmethod
    def resolve_images(root: models.ProductVariant, *_args):
        return root.images.all()

    @classmethod
    def get_node(cls, info, id):
        user = info.context.user
        visible_products = models.Product.objects.visible_to_user(user).values_list(
            "pk", flat=True
        )
        qs = cls._meta.model.objects.filter(product__id__in=visible_products)
        return cls.maybe_optimize(info, qs, id)

    @staticmethod
    @permission_required("product.manage_products")
    def resolve_private_meta(root, _info):
        return resolve_private_meta(root, _info)

    @staticmethod
    def resolve_meta(root, _info):
        return resolve_meta(root, _info)


class Product(CountableDjangoObjectType, MetadataObjectType):
    url = graphene.String(
        description="The storefront URL for the product.", required=True
    )
    thumbnail = graphene.Field(
        Image,
        description="The main thumbnail for a product.",
        size=graphene.Argument(graphene.Int, description="Size of thumbnail."),
    )
    availability = graphene.Field(
        ProductPricingInfo,
        description=(
            "Informs about product's availability in the storefront, current price and "
            "discounts."
        ),
        deprecation_reason=(
            "DEPRECATED: Will be removed in Saleor 2.10, Has been renamed to `pricing`."
        ),
    )
    pricing = graphene.Field(
        ProductPricingInfo,
        description=(
            "Lists the storefront product's pricing, the current price and discounts, "
            "only meant for displaying."
        ),
    )
    is_available = graphene.Boolean(
        description="Whether the product is in stock and visible or not."
    )
    base_price = graphene.Field(Money, description="The product's default base price.")
    price = graphene.Field(
        Money,
        description="The product's default base price.",
        deprecation_reason=(
            "DEPRECATED: Will be removed in Saleor 2.10, has been replaced by "
            "`basePrice`"
        ),
    )
    minimal_variant_price = graphene.Field(
        Money, description="The price of the cheapest variant (including discounts)."
    )
    tax_type = graphene.Field(
        TaxType, description="A type of tax. Assigned by enabled tax gateway"
    )
    attributes = graphene.List(
        graphene.NonNull(SelectedAttribute),
        required=True,
        description="List of attributes assigned to this product.",
    )
    purchase_cost = graphene.Field(MoneyRange)
    margin = graphene.Field(Margin)
    image_by_id = graphene.Field(
        lambda: ProductImage,
        id=graphene.Argument(graphene.ID, description="ID of a product image."),
        description="Get a single product image by ID.",
    )
    variants = gql_optimizer.field(
        graphene.List(ProductVariant, description="List of variants for the product."),
        model_field="variants",
    )
    images = gql_optimizer.field(
        graphene.List(
            lambda: ProductImage, description="List of images for the product."
        ),
        model_field="images",
    )
    collections = gql_optimizer.field(
        graphene.List(
            lambda: Collection, description="List of collections for the product."
        ),
        model_field="collections",
    )
    translation = graphene.Field(
        ProductTranslation,
        language_code=graphene.Argument(
            LanguageCodeEnum,
            description="A language code to return the translation for.",
            required=True,
        ),
        description=("Returns translated Product fields for the given language code."),
        resolver=resolve_translation,
    )

    slug = graphene.String(required=True, description="The slug of a product.")

    class Meta:
        description = "Represents an individual item for sale in the storefront."
        interfaces = [relay.Node]
        model = models.Product
        only_fields = [
            "category",
            "charge_taxes",
            "description",
            "description_json",
            "id",
            "is_published",
            "name",
            "product_type",
            "publication_date",
            "seo_description",
            "seo_title",
            "updated_at",
            "weight",
        ]

    @staticmethod
    def resolve_tax_type(root: models.Product, info):
        tax_data = info.context.extensions.get_tax_code_from_object_meta(root)
        return TaxType(tax_code=tax_data.code, description=tax_data.description)

    @staticmethod
    @gql_optimizer.resolver_hints(prefetch_related="images")
    def resolve_thumbnail(root: models.Product, info, *, size=255):
        image = root.get_first_image()
        if image:
            url = get_product_image_thumbnail(image, size, method="thumbnail")
            alt = image.alt
            return Image(alt=alt, url=info.context.build_absolute_uri(url))
        return None

    @staticmethod
    def resolve_url(root: models.Product, *_args):
        return root.get_absolute_url()

    @staticmethod
    @gql_optimizer.resolver_hints(
        prefetch_related=("variants", "collections"),
        only=["publication_date", "charge_taxes", "price_amount", "currency", "meta"],
    )
    def resolve_pricing(root: models.Product, info):
        context = info.context
        availability = get_product_availability(
            root,
            context.discounts,
            context.country,
            context.currency,
            context.extensions,
        )
        return ProductPricingInfo(**availability._asdict())

    resolve_availability = resolve_pricing

    @staticmethod
    @gql_optimizer.resolver_hints(prefetch_related=("variants"))
    def resolve_is_available(root: models.Product, _info):
        return root.is_available

    @staticmethod
    @permission_required("product.manage_products")
    def resolve_base_price(root: models.Product, _info):
        return root.price

    @staticmethod
    @gql_optimizer.resolver_hints(
        prefetch_related=("variants", "collections"),
        only=["publication_date", "charge_taxes", "price_amount", "currency", "meta"],
    )
    def resolve_price(root: models.Product, info):
        price_range = root.get_price_range(info.context.discounts)
        price = info.context.extensions.apply_taxes_to_product(
            root, price_range.start, info.context.country
        )
        return price.net

    @staticmethod
    @gql_optimizer.resolver_hints(
        prefetch_related=[
            "product_type__attributeproduct__productassignments__values",
            "product_type__attributeproduct__attribute",
        ]
    )
    def resolve_attributes(root: models.Product, info):
        return resolve_attribute_list(root, user=info.context.user)

    @staticmethod
    @permission_required("product.manage_products")
    def resolve_purchase_cost(root: models.Product, *_args):
        purchase_cost, _ = get_product_costs_data(root)
        return purchase_cost

    @staticmethod
    @permission_required("product.manage_products")
    def resolve_margin(root: models.Product, *_args):
        _, margin = get_product_costs_data(root)
        return Margin(margin[0], margin[1])

    @staticmethod
    def resolve_image_by_id(root: models.Product, info, id):
        pk = get_database_id(info, id, ProductImage)
        try:
            return root.images.get(pk=pk)
        except models.ProductImage.DoesNotExist:
            raise GraphQLError("Product image not found.")

    @staticmethod
    @gql_optimizer.resolver_hints(model_field="images")
    def resolve_images(root: models.Product, *_args, **_kwargs):
        return root.images.all()

    @staticmethod
    def resolve_variants(root: models.Product, *_args, **_kwargs):
        return root.variants.all()

    @staticmethod
    def resolve_collections(root: models.Product, *_args):
        return root.collections.all()

    @classmethod
    def get_node(cls, info, pk):
        if info.context:
            qs = cls._meta.model.objects.visible_to_user(info.context.user)
            return cls.maybe_optimize(info, qs, pk)
        return None

    @staticmethod
    @permission_required("product.manage_products")
    def resolve_private_meta(root, _info):
        return resolve_private_meta(root, _info)

    @staticmethod
    def resolve_meta(root, _info):
        return resolve_meta(root, _info)

    @staticmethod
    def resolve_slug(root: models.Product, *_args):
        return root.get_slug()


class ProductType(CountableDjangoObjectType, MetadataObjectType):
    products = gql_optimizer.field(
        PrefetchingConnectionField(
            Product, description="List of products of this type."
        ),
        prefetch_related=prefetch_products,
    )
    tax_rate = TaxRateType(description="A type of tax rate.")
    tax_type = graphene.Field(
        TaxType, description="A type of tax. Assigned by enabled tax gateway"
    )
    variant_attributes = graphene.List(
        Attribute, description="Variant attributes of that product type."
    )
    product_attributes = graphene.List(
        Attribute, description="Product attributes of that product type."
    )
    available_attributes = gql_optimizer.field(
        FilterInputConnectionField(Attribute, filter=AttributeFilterInput())
    )

    class Meta:
        description = (
            "Represents a type of product. It defines what attributes are available to "
            "products of this type."
        )
        interfaces = [relay.Node]
        model = models.ProductType
        only_fields = [
            "has_variants",
            "id",
            "is_digital",
            "is_shipping_required",
            "name",
            "weight",
            "tax_type",
        ]

    @staticmethod
    def resolve_tax_type(root: models.ProductType, info):
        tax_data = info.context.extensions.get_tax_code_from_object_meta(root)
        return TaxType(tax_code=tax_data.code, description=tax_data.description)

    @staticmethod
    def resolve_tax_rate(root: models.ProductType, info, **_kwargs):
        # FIXME this resolver should be dropped after we drop tax_rate from API
        if not hasattr(root, "meta"):
            return None
        tax = root.meta.get("taxes", {}).get("vatlayer", {})
        return tax.get("code")

    @staticmethod
    @gql_optimizer.resolver_hints(
        prefetch_related="product_attributes__attributeproduct"
    )
    def resolve_product_attributes(root: models.ProductType, *_args, **_kwargs):
        return root.product_attributes.product_attributes_sorted().all()

    @staticmethod
    @gql_optimizer.resolver_hints(
        prefetch_related="variant_attributes__attributevariant"
    )
    def resolve_variant_attributes(root: models.ProductType, *_args, **_kwargs):
        return root.variant_attributes.variant_attributes_sorted().all()

    @staticmethod
    def resolve_products(root: models.ProductType, info, **_kwargs):
        if hasattr(root, "prefetched_products"):
            return root.prefetched_products
        qs = root.products.visible_to_user(info.context.user)
        return gql_optimizer.query(qs, info)

    @staticmethod
    @permission_required("product.manage_products")
    def resolve_available_attributes(root: models.ProductType, info, **kwargs):
        qs = models.Attribute.objects.get_unassigned_attributes(root.pk)
        return resolve_attributes(info, qs=qs, **kwargs)

    @staticmethod
    @permission_required("account.manage_products")
    def resolve_private_meta(root, _info):
        return resolve_private_meta(root, _info)

    @staticmethod
    def resolve_meta(root, _info):
        return resolve_meta(root, _info)


class Collection(CountableDjangoObjectType, MetadataObjectType):
    products = gql_optimizer.field(
        PrefetchingConnectionField(
            Product, description="List of products in this collection."
        ),
        prefetch_related=prefetch_products_collection_sorted,
    )
    background_image = graphene.Field(
        Image, size=graphene.Int(description="Size of the image.")
    )
    translation = graphene.Field(
        CollectionTranslation,
        language_code=graphene.Argument(
            LanguageCodeEnum,
            description="A language code to return the translation for.",
            required=True,
        ),
        description=(
            "Returns translated Collection fields " "for the given language code."
        ),
        resolver=resolve_translation,
    )

    class Meta:
        description = "Represents a collection of products."
        only_fields = [
            "description",
            "description_json",
            "id",
            "is_published",
            "name",
            "publication_date",
            "seo_description",
            "seo_title",
            "slug",
        ]
        interfaces = [relay.Node]
        model = models.Collection

    @staticmethod
    def resolve_background_image(root: models.Collection, info, size=None, **_kwargs):
        if root.background_image:
            return Image.get_adjusted(
                image=root.background_image,
                alt=root.background_image_alt,
                size=size,
                rendition_key_set="background_images",
                info=info,
            )

    @staticmethod
    def resolve_products(root: models.Collection, info, **_kwargs):
        if hasattr(root, "prefetched_products"):
            return root.prefetched_products
        qs = root.products.collection_sorted(info.context.user)
        return gql_optimizer.query(qs, info)

    @classmethod
    def get_node(cls, info, id):
        if info.context:
            user = info.context.user
            qs = cls._meta.model.objects.visible_to_user(user)
            return cls.maybe_optimize(info, qs, id)
        return None

    @staticmethod
    @permission_required("product.manage_products")
    def resolve_private_meta(root, _info):
        return resolve_private_meta(root, _info)

    @staticmethod
    def resolve_meta(root, _info):
        return resolve_meta(root, _info)


class Category(CountableDjangoObjectType, MetadataObjectType):
    ancestors = PrefetchingConnectionField(
        lambda: Category, description="List of ancestors of the category."
    )
    products = gql_optimizer.field(
        PrefetchingConnectionField(
            Product, description="List of products in the category."
        ),
        prefetch_related=prefetch_products,
    )
    url = graphene.String(description="The storefront's URL for the category.")
    children = PrefetchingConnectionField(
        lambda: Category, description="List of children of the category."
    )
    background_image = graphene.Field(
        Image, size=graphene.Int(description="Size of the image.")
    )
    translation = graphene.Field(
        CategoryTranslation,
        language_code=graphene.Argument(
            LanguageCodeEnum,
            description="A language code to return the translation for.",
            required=True,
        ),
        description=("Returns translated Category fields for the given language code."),
        resolver=resolve_translation,
    )

    class Meta:
        description = (
            "Represents a single category of products. Categories allow to organize "
            "products in a tree-hierarchies which can be used for navigation in the "
            "storefront."
        )
        only_fields = [
            "description",
            "description_json",
            "id",
            "level",
            "name",
            "parent",
            "seo_description",
            "seo_title",
            "slug",
        ]
        interfaces = [relay.Node]
        model = models.Category

    @staticmethod
    def resolve_ancestors(root: models.Category, info, **_kwargs):
        qs = root.get_ancestors()
        return gql_optimizer.query(qs, info)

    @staticmethod
    def resolve_background_image(root: models.Category, info, size=None, **_kwargs):
        if root.background_image:
            return Image.get_adjusted(
                image=root.background_image,
                alt=root.background_image_alt,
                size=size,
                rendition_key_set="background_images",
                info=info,
            )

    @staticmethod
    def resolve_children(root: models.Category, info, **_kwargs):
        qs = root.children.all()
        return gql_optimizer.query(qs, info)

    @staticmethod
    def resolve_url(root: models.Category, _info):
        return root.get_absolute_url()

    @staticmethod
    def resolve_products(root: models.Category, info, **_kwargs):
        # If the category has no children, we use the prefetched data.
        children = root.children.all()
        if not children and hasattr(root, "prefetched_products"):
            return root.prefetched_products

        # Otherwise we want to include products from child categories which
        # requires performing additional logic.
        tree = root.get_descendants(include_self=True)
        qs = models.Product.objects.published()
        qs = qs.filter(category__in=tree)
        return gql_optimizer.query(qs, info)

    @staticmethod
    @permission_required("product.manage_products")
    def resolve_private_meta(root, _info):
        return resolve_private_meta(root, _info)

    @staticmethod
    def resolve_meta(root, _info):
        return resolve_meta(root, _info)


class ProductImage(CountableDjangoObjectType):
    url = graphene.String(
        required=True,
        description="The URL of the image.",
        size=graphene.Int(description="Size of the image."),
    )

    class Meta:
        description = "Represents a product image."
        only_fields = ["alt", "id", "sort_order"]
        interfaces = [relay.Node]
        model = models.ProductImage

    @staticmethod
    def resolve_url(root: models.ProductImage, info, *, size=None):
        if size:
            url = get_thumbnail(root.image, size, method="thumbnail")
        else:
            url = root.image.url
        return info.context.build_absolute_uri(url)


class MoveProductInput(graphene.InputObjectType):
    product_id = graphene.ID(
        description="The ID of the product to move.", required=True
    )
    sort_order = graphene.Int(
        description=(
            "The relative sorting position of the product (from -inf to +inf) "
            "starting from the first given product's actual position."
        )
    )
