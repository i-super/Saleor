import graphene
from django.conf import settings

from ...discount import models as discount_models
from ...menu import models as menu_models
from ...page import models as page_models
from ...product import models as product_models
from ...shipping import models as shipping_models
from ...site import models as site_models
from ..core.connection import CountableDjangoObjectType
from ..core.types import LanguageDisplay
from ..core.utils import str_to_enum
from ..decorators import permission_required
from .enums import LanguageCodeEnum
from .resolvers import resolve_translation

BASIC_TRANSLATABLE_FIELDS = ["id", "name"]
EXTENDED_TRANSLATABLE_FIELDS = [
    "id",
    "name",
    "description",
    "description_json",
    "seo_title",
    "seo_description",
]


class BaseTranslationType(CountableDjangoObjectType):
    language = graphene.Field(
        LanguageDisplay, description="Translation language.", required=True
    )

    class Meta:
        abstract = True

    @staticmethod
    def resolve_language(root, *_args):
        try:
            language = next(
                language[1]
                for language in settings.LANGUAGES
                if language[0] == root.language_code
            )
        except StopIteration:
            return None
        return LanguageDisplay(
            code=LanguageCodeEnum[str_to_enum(root.language_code)], language=language
        )


class AttributeValueTranslation(BaseTranslationType):
    class Meta:
        model = product_models.AttributeValueTranslation
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS


class AttributeValueTranslatableContent(CountableDjangoObjectType):
    translation = graphene.Field(
        AttributeValueTranslation,
        language_code=graphene.Argument(
            LanguageCodeEnum,
            description="A language code to return the translation for.",
            required=True,
        ),
        description=(
            "Returns translated Attribute Value fields for the given language code."
        ),
        resolver=resolve_translation,
    )
    attribute_value = graphene.Field(
        "saleor.graphql.product.types.attributes.AttributeValue",
        description="Represents a value of an attribute.",
    )

    class Meta:
        model = product_models.AttributeValue
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS

    def resolve_attribute_value(self, info):
        return self


class AttributeTranslation(BaseTranslationType):
    class Meta:
        model = product_models.AttributeTranslation
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS


class AttributeTranslatableContent(CountableDjangoObjectType):
    translation = graphene.Field(
        AttributeTranslation,
        language_code=graphene.Argument(
            LanguageCodeEnum,
            description="A language code to return the translation for.",
            required=True,
        ),
        description=(
            "Returns translated Attribute fields for the given language code."
        ),
        resolver=resolve_translation,
    )
    attribute = graphene.Field(
        "saleor.graphql.product.types.attributes.Attribute",
        description="Custom attribute of a product.",
    )

    class Meta:
        model = product_models.Attribute
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS

    def resolve_attribute(self, info):
        return self


class ProductVariantTranslation(BaseTranslationType):
    class Meta:
        model = product_models.ProductVariantTranslation
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS


class ProductVariantTranslatableContent(CountableDjangoObjectType):
    translation = graphene.Field(
        ProductVariantTranslation,
        language_code=graphene.Argument(
            LanguageCodeEnum,
            description="A language code to return the translation for.",
            required=True,
        ),
        description=(
            "Returns translated Product Variant fields for the given language code."
        ),
        resolver=resolve_translation,
    )
    product_variant = graphene.Field(
        "saleor.graphql.product.types.products.ProductVariant",
        description=(
            "Represents a version of a product such as different size or color."
        ),
    )

    class Meta:
        model = product_models.ProductVariant
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS

    def resolve_product_variant(self, info):
        visible_products = product_models.Product.objects.visible_to_user(
            info.context.user
        ).values_list("pk", flat=True)
        return product_models.ProductVariant.objects.filter(
            product__id__in=visible_products, pk=self.id
        ).first()


class ProductTranslation(BaseTranslationType):
    class Meta:
        model = product_models.ProductTranslation
        interfaces = [graphene.relay.Node]
        only_fields = EXTENDED_TRANSLATABLE_FIELDS


class ProductTranslatableContent(CountableDjangoObjectType):
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
    product = graphene.Field(
        "saleor.graphql.product.types.products.Product",
        description="Represents an individual item for sale in the storefront.",
    )

    class Meta:
        model = product_models.Product
        interfaces = [graphene.relay.Node]
        only_fields = EXTENDED_TRANSLATABLE_FIELDS

    def resolve_product(self, info):
        return (
            product_models.Product.objects.visible_to_user(info.context.user)
            .filter(pk=self.id)
            .first()
        )


class CollectionTranslation(BaseTranslationType):
    class Meta:
        model = product_models.CollectionTranslation
        interfaces = [graphene.relay.Node]
        only_fields = EXTENDED_TRANSLATABLE_FIELDS


class CollectionTranslatableContent(CountableDjangoObjectType):
    translation = graphene.Field(
        CollectionTranslation,
        language_code=graphene.Argument(
            LanguageCodeEnum,
            description="A language code to return the translation for.",
            required=True,
        ),
        description=(
            "Returns translated Collection fields for the given language code."
        ),
        resolver=resolve_translation,
    )
    collection = graphene.Field(
        "saleor.graphql.product.types.products.Collection",
        description="Represents a collection of products.",
    )

    class Meta:
        model = product_models.Collection
        interfaces = [graphene.relay.Node]
        only_fields = EXTENDED_TRANSLATABLE_FIELDS

    def resolve_collection(self, info):
        return (
            product_models.Collection.objects.visible_to_user(info.context.user)
            .filter(pk=self.id)
            .first()
        )


class CategoryTranslation(BaseTranslationType):
    class Meta:
        model = product_models.CategoryTranslation
        interfaces = [graphene.relay.Node]
        only_fields = EXTENDED_TRANSLATABLE_FIELDS


class CategoryTranslatableContent(CountableDjangoObjectType):
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
    category = graphene.Field(
        "saleor.graphql.product.types.products.Category",
        description="Represents a single category of products.",
    )

    class Meta:
        model = product_models.Category
        interfaces = [graphene.relay.Node]
        only_fields = EXTENDED_TRANSLATABLE_FIELDS

    def resolve_category(self, info):
        return self


class PageTranslation(BaseTranslationType):
    class Meta:
        model = page_models.PageTranslation
        interfaces = [graphene.relay.Node]
        only_fields = [
            "content",
            "content_json",
            "id",
            "seo_description",
            "seo_title",
            "title",
        ]


class PageTranslatableContent(CountableDjangoObjectType):
    translation = graphene.Field(
        PageTranslation,
        language_code=graphene.Argument(
            LanguageCodeEnum,
            description="A language code to return the translation for.",
            required=True,
        ),
        description="Returns translated Page fields for the given language code.",
        resolver=resolve_translation,
    )
    page = graphene.Field(
        "saleor.graphql.page.types.Page",
        description=(
            "A static page that can be manually added by a shop operator ",
            "through the dashboard.",
        ),
    )

    class Meta:
        model = page_models.Page
        interfaces = [graphene.relay.Node]
        only_fields = [
            "content",
            "content_json",
            "id",
            "seo_description",
            "seo_title",
            "title",
        ]

    def resolve_page(self, info):
        return (
            page_models.Page.objects.visible_to_user(info.context.user)
            .filter(pk=self.id)
            .first()
        )


class VoucherTranslation(BaseTranslationType):
    class Meta:
        model = discount_models.VoucherTranslation
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS


class VoucherTranslatableContent(CountableDjangoObjectType):
    translation = graphene.Field(
        VoucherTranslation,
        language_code=graphene.Argument(
            LanguageCodeEnum,
            description="A language code to return the translation for.",
            required=True,
        ),
        description="Returns translated Voucher fields for the given language code.",
        resolver=resolve_translation,
    )
    voucher = graphene.Field(
        "saleor.graphql.discount.types.Voucher",
        # TODO consider move description to variable. Issue #4957
        description=(
            "Vouchers allow giving discounts to particular customers on categories, "
            "collections or specific products. They can be used during checkout by "
            "providing valid voucher codes."
        ),
    )

    class Meta:
        model = discount_models.Voucher
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS

    @permission_required("discount.manage_discounts")
    def resolve_voucher(self, info):
        return self


class SaleTranslation(BaseTranslationType):
    class Meta:
        model = discount_models.SaleTranslation
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS


class SaleTranslatableContent(CountableDjangoObjectType):
    translation = graphene.Field(
        SaleTranslation,
        language_code=graphene.Argument(
            LanguageCodeEnum,
            description="A language code to return the translation for.",
            required=True,
        ),
        description="Returns translated sale fields for the given language code.",
        resolver=resolve_translation,
    )
    sale = graphene.Field(
        "saleor.graphql.discount.types.Sale",
        description=(
            "Sales allow creating discounts for categories, collections "
            "or products and are visible to all the customers."
        ),
    )

    class Meta:
        model = discount_models.Sale
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS

    @permission_required("discount.manage_discounts")
    def resolve_sale(self, info):
        return self


class ShopTranslation(BaseTranslationType):
    class Meta:
        model = site_models.SiteSettingsTranslation
        interfaces = [graphene.relay.Node]
        only_fields = ["description", "header_text", "id"]


class MenuItemTranslation(BaseTranslationType):
    class Meta:
        model = menu_models.MenuItemTranslation
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS


class MenuItemTranslatableContent(CountableDjangoObjectType):
    translation = graphene.Field(
        MenuItemTranslation,
        language_code=graphene.Argument(
            LanguageCodeEnum,
            description="A language code to return the translation for.",
            required=True,
        ),
        description=(
            "Returns translated Menu item fields for the given language code."
        ),
        resolver=resolve_translation,
    )
    menu_item = graphene.Field(
        "saleor.graphql.menu.types.MenuItem",
        description=(
            "Represents a single item of the related menu. Can store categories, "
            "collection or pages."
        ),
    )

    class Meta:
        model = menu_models.MenuItem
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS

    def resolve_menu_item(self, info):
        return self


class ShippingMethodTranslation(BaseTranslationType):
    class Meta:
        model = shipping_models.ShippingMethodTranslation
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS


class ShippingMethodTranslatableContent(CountableDjangoObjectType):
    translation = graphene.Field(
        ShippingMethodTranslation,
        language_code=graphene.Argument(
            LanguageCodeEnum,
            description="A language code to return the translation for.",
            required=True,
        ),
        description=(
            "Returns translated shipping method fields for the given language code."
        ),
        resolver=resolve_translation,
    )
    shipping_method = graphene.Field(
        "saleor.graphql.shipping.types.ShippingMethod",
        description=(
            "Shipping method are the methods you'll use to get customer's orders "
            " to them. They are directly exposed to the customers."
        ),
    )

    class Meta:
        model = shipping_models.ShippingMethod
        interfaces = [graphene.relay.Node]
        only_fields = BASIC_TRANSLATABLE_FIELDS

    @permission_required("shipping.manage_shipping")
    def resolve_shipping_method(self, info):
        return self
