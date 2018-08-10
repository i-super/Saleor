import graphene
from django.template.defaultfilters import slugify
from graphene.types import InputObjectType
from graphql_jwt.decorators import permission_required

from ....product import models
from ....product.utils.attributes import get_name_from_attributes
from ...core.mutations import BaseMutation, ModelDeleteMutation, ModelMutation
from ...core.types.common import Decimal, Error, SeoInput
from ...core.utils import clean_seo_fields
from ...file_upload.types import Upload
from ...utils import get_attributes_dict_from_list, get_node, get_nodes
from ..types import Collection, Product, ProductImage, ProductVariant


def update_variants_names(instance, saved_attributes):
    initial_attributes = set(instance.variant_attributes.all())
    attributes_changed = initial_attributes.intersection(saved_attributes)
    if not attributes_changed:
        return
    variants_to_be_updated = models.ProductVariant.objects.filter(
        product__in=instance.products.all(),
        product__product_type__variant_attributes__in=attributes_changed)
    variants_to_be_updated = variants_to_be_updated.prefetch_related(
        'product__product_type__variant_attributes__values').all()
    attributes = instance.variant_attributes.all()
    for variant in variants_to_be_updated:
        variant.name = get_name_from_attributes(variant, attributes)
        variant.save()


class CategoryInput(graphene.InputObjectType):
    description = graphene.String(description='Category description')
    name = graphene.String(description='Category name')
    parent = graphene.ID(
        description='''
        ID of the parent category. If empty, category will be top level
        category.''', name='parent')
    slug = graphene.String(description='Category slug')
    seo = SeoInput(description='Search engine optimization fields.')


class CategoryCreate(ModelMutation):
    class Arguments:
        input = CategoryInput(
            required=True, description='Fields required to create a category.')

    class Meta:
        description = 'Creates a new category.'
        model = models.Category

    @classmethod
    def clean_input(cls, info, instance, input, errors):
        cleaned_input = super().clean_input(info, instance, input, errors)
        if 'slug' not in cleaned_input:
            cleaned_input['slug'] = slugify(cleaned_input['name'])
        clean_seo_fields(cleaned_input)
        return cleaned_input

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('product.manage_products')


class CategoryUpdate(CategoryCreate):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of a category to update.')
        input = CategoryInput(
            required=True, description='Fields required to update a category.')

    class Meta:
        description = 'Updates a category.'
        model = models.Category


class CategoryDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of a category to delete.')

    class Meta:
        description = 'Deletes a category.'
        model = models.Category

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('product.manage_products')


class CollectionInput(graphene.InputObjectType):
    is_published = graphene.Boolean(
        description='Informs whether a collection is published.')
    name = graphene.String(description='Name of the collection.')
    slug = graphene.String(description='Slug of the collection.')
    products = graphene.List(
        graphene.ID,
        description='List of products to be added to the collection.',
        name='products')
    background_image = Upload(description='Background image file.')
    seo = SeoInput(description='Search engine optimization fields.')


class CollectionCreate(ModelMutation):
    class Arguments:
        input = CollectionInput(
            required=True,
            description='Fields required to create a collection.')

    class Meta:
        description = 'Creates a new collection.'
        model = models.Collection

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('product.manage_products')

    @classmethod
    def clean_input(cls, info, instance, input, errors):
        cleaned_input = super().clean_input(info, instance, input, errors)
        clean_seo_fields(cleaned_input)
        return cleaned_input


class CollectionUpdate(CollectionCreate):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of a collection to update.')
        input = CollectionInput(
            required=True,
            description='Fields required to update a collection.')

    class Meta:
        description = 'Updates a collection.'
        model = models.Collection


class CollectionDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of a collection to delete.')

    class Meta:
        description = 'Deletes a collection.'
        model = models.Collection

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('product.manage_products')


class CollectionAddProducts(BaseMutation):
    class Arguments:
        collection_id = graphene.Argument(
            graphene.ID, required=True,
            description='ID of a collection.')
        products = graphene.List(
            graphene.ID, required=True,
            description='List of product IDs.')

    collection = graphene.Field(
        Collection,
        description='Collection to which products will be added.')

    class Meta:
        description = 'Adds products to a collection.'

    @permission_required('product.manage_products')
    def mutate(self, info, collection_id, products):
        collection = get_node(info, collection_id, only_type=Collection)
        products = get_nodes(products, Product)
        collection.products.add(*products)
        return CollectionAddProducts(collection=collection)


class CollectionRemoveProducts(BaseMutation):
    class Arguments:
        collection_id = graphene.Argument(
            graphene.ID, required=True, description='ID of a collection.')
        products = graphene.List(
            graphene.ID, required=True, description='List of product IDs.')

    collection = graphene.Field(
        Collection,
        description='Collection from which products will be removed.')

    class Meta:
        description = 'Remove products from a collection.'

    @permission_required('product.manage_products')
    def mutate(self, info, collection_id, products):
        collection = get_node(info, collection_id, only_type=Collection)
        products = get_nodes(products, Product)
        collection.products.remove(*products)
        return CollectionRemoveProducts(collection=collection)


class AttributeValueInput(InputObjectType):
    slug = graphene.String(
        required=True, description='Slug of an attribute.')
    value = graphene.String(
        required=True, description='Value of an attribute.')


class ProductInput(graphene.InputObjectType):
    attributes = graphene.List(
        AttributeValueInput,
        description='List of product attributes.')
    available_on = graphene.types.datetime.Date(
        description='Publication date. ISO 8601 standard.')
    category = graphene.ID(
        description='ID of the product\'s category.', name='category')
    charge_taxes = graphene.Boolean(
        description='Determine if taxes are being charged for the product.')
    collections = graphene.List(
        graphene.ID,
        description='List of IDs of collections that the product belongs to.',
        name='collections')
    description = graphene.String(description='Product description.')
    is_published = graphene.Boolean(
        description='Determines if product is visible to customers.')
    name = graphene.String(description='Product name.')
    product_type = graphene.ID(
        description='ID of the type that product belongs to.',
        name='productType')
    price = Decimal(description='Product price.')
    tax_rate = graphene.String(description='Tax rate.')
    seo = SeoInput(description='Search engine optimization fields.')


class ProductCreate(ModelMutation):
    class Arguments:
        input = ProductInput(
            required=True, description='Fields required to create a product.')

    class Meta:
        description = 'Creates a new product.'
        model = models.Product

    @classmethod
    def clean_input(cls, info, instance, input, errors):
        cleaned_input = super().clean_input(info, instance, input, errors)
        # Attributes are provided as list of `AttributeValueInput` objects.
        # We need to transform them into the format they're stored in the
        # `Product` model, which is HStore field that maps attribute's PK to
        # the value's PK.

        attributes = cleaned_input.pop('attributes', [])
        product_type = (
            instance.product_type
            if instance.pk else cleaned_input.get('product_type'))

        if attributes and product_type:
            slug_to_id_map = dict(
                product_type.product_attributes.values_list('slug', 'id'))
            attributes = get_attributes_dict_from_list(
                attributes, slug_to_id_map)
            cleaned_input['attributes'] = attributes
        clean_seo_fields(cleaned_input)
        return cleaned_input

    @classmethod
    def _save_m2m(cls, info, instance, cleaned_data):
        collections = cleaned_data.get('collections', None)
        if collections is not None:
            instance.collections.set(collections)

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('product.manage_products')


class ProductUpdate(ProductCreate):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of a product to update.')
        input = ProductInput(
            required=True, description='Fields required to update a product.')

    class Meta:
        description = 'Updates an existing product.'
        model = models.Product


class ProductDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of a product to delete.')

    class Meta:
        description = 'Deletes a product.'
        model = models.Product

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('product.manage_products')


class ProductVariantInput(graphene.InputObjectType):
    attributes = graphene.List(
        AttributeValueInput,
        description='List of attributes specific to this variant.')
    cost_price = Decimal(description='Cost price of the variant.')
    price_override = Decimal(
        description='Special price of the particular variant.')
    product = graphene.ID(
        description='Product ID of which type is the variant.',
        name='product')
    sku = graphene.String(description='Stock keeping unit.')
    quantity = graphene.Int(
        description='The total quantity of this variant available for sale.')
    track_inventory = graphene.Boolean(
        description="""Determines if the inventory of this variant should
        be tracked. If false, the quantity won't change when customers
        buy this item.""")


class ProductVariantCreate(ModelMutation):
    class Arguments:
        input = ProductVariantInput(
            required=True,
            description='Fields required to create a product variant.')

    class Meta:
        description = 'Creates a new variant for a product'
        model = models.ProductVariant

    @classmethod
    def clean_input(cls, info, instance, input, errors):
        cleaned_input = super().clean_input(info, instance, input, errors)

        # Attributes are provided as list of `AttributeValueInput` objects.
        # We need to transform them into the format they're stored in the
        # `Product` model, which is HStore field that maps attribute's PK to
        # the value's PK.

        attributes = cleaned_input.pop('attributes', [])
        product = instance.product if instance.pk else cleaned_input.get(
            'product')
        product_type = product.product_type

        if attributes and product_type:
            slug_to_id_map = dict(
                product_type.variant_attributes.values_list('slug', 'id'))
            attributes = get_attributes_dict_from_list(
                attributes, slug_to_id_map)
            cleaned_input['attributes'] = attributes
        return cleaned_input

    @classmethod
    def save(cls, info, instance, cleaned_input):
        attributes = instance.product.product_type.variant_attributes.all()
        instance.name = get_name_from_attributes(instance, attributes)
        instance.save()

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('product.manage_products')


class ProductVariantUpdate(ProductVariantCreate):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of a product variant to update.')
        input = ProductVariantInput(
            required=True,
            description='Fields required to update a product variant.')

    class Meta:
        description = 'Updates an existing variant for product'
        model = models.ProductVariant


class ProductVariantDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of a product variant to delete.')

    class Meta:
        description = 'Deletes a product variant.'
        model = models.ProductVariant

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('product.manage_products')


class ProductTypeInput(graphene.InputObjectType):
    name = graphene.String(description='Name of the product type.')
    has_variants = graphene.Boolean(
        description="""Determines if product of this type has multiple
        variants. This option mainly simplifies product management
        in the dashboard. There is always at least one variant created under
        the hood.""")
    product_attributes = graphene.List(
        graphene.ID,
        description='List of attributes shared among all product variants.',
        name='productAttributes')
    variant_attributes = graphene.List(
        graphene.ID,
        description="""List of attributes used to distinguish between
        different variants of a product.""",
        name='variantAttributes')
    is_shipping_required = graphene.Boolean(
        description="""Determines if shipping is required for products
        of this variant.""")


class ProductTypeCreate(ModelMutation):
    class Arguments:
        input = ProductTypeInput(
            required=True,
            description='Fields required to create a product type.')

    class Meta:
        description = 'Creates a new product type.'
        model = models.ProductType

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('product.manage_products')


class ProductTypeUpdate(ProductTypeCreate):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of a product type to update.')
        input = ProductTypeInput(
            required=True,
            description='Fields required to update a product type.')

    class Meta:
        description = 'Updates an existing product type.'
        model = models.ProductType

    @classmethod
    def save(cls, info, instance, cleaned_input):
        variant_attr = cleaned_input.get('variant_attributes')
        if variant_attr:
            variant_attr = set(variant_attr)
            update_variants_names(instance, variant_attr)
        super().save(info, instance, cleaned_input)


class ProductTypeDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of a product type to delete.')

    class Meta:
        description = 'Deletes a product type.'
        model = models.ProductType

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('product.manage_products')


class ProductImageCreateInput(graphene.InputObjectType):
    alt = graphene.String(description='Alt text for an image.')
    image = Upload(
        required=True,
        description='Represents an image file in a multipart request.')
    product = graphene.ID(description='ID of an product.', name='product')


class ProductImageCreate(ModelMutation):
    class Arguments:
        input = ProductImageCreateInput(
            required=True,
            description='Fields required to create a product image.')

    class Meta:
        description = '''Create a product image. This mutation must be sent
        as a `multipart` request. More detailed specs of the upload format can
        be found here: https://github.com/jaydenseric/graphql-multipart-request-spec'''
        model = models.ProductImage

    @classmethod
    def clean_input(cls, info, instance, input, errors):
        cleaned_input = super().clean_input(info, instance, input, errors)
        uploaded_image = cleaned_input['image']
        if not uploaded_image.content_type.startswith('image/'):
            cls.add_error(errors, 'image', 'Invalid file type')
        return cleaned_input

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('product.manage_products')


class ProductImageUpdateInput(graphene.InputObjectType):
    alt = graphene.String(description='Alt text for an image.')


class ProductImageUpdate(ModelMutation):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of a product image to update.')
        input = ProductImageUpdateInput(
            required=True,
            description='Fields required to update a product image.')

    class Meta:
        description = 'Updates a product image.'
        model = models.ProductImage

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('product.manage_products')


class ProductImageReorder(BaseMutation):
    class Arguments:
        product_id = graphene.ID(
            required=True,
            description='Id of product that images order will be altered.')
        images_ids = graphene.List(
            graphene.ID, required=True,
            description='IDs of a product images in the desired order.')

    class Meta:
        description = 'Changes ordering of the product image.'

    product_images = graphene.List(
        ProductImage,
        description='Product image which sort order will be altered.')

    @classmethod
    @permission_required('product.manage_products')
    def mutate(cls, root, info, product_id, images_ids):
        product = get_node(info, product_id, Product)
        if len(images_ids) != product.images.count():
            return cls(
                errors=[
                    Error(field='order',
                          message='Incorrect number of image IDs provided.')])
        for order, image_id in enumerate(images_ids):
            image = get_node(info, image_id, only_type=ProductImage)
            image.sort_order = order
            image.save()
        product_images = get_nodes(images_ids, ProductImage)
        return ProductImageReorder(product_images=product_images)


class ProductImageDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of a product image to delete.')

    class Meta:
        description = 'Deletes a product image.'
        model = models.ProductImage

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('product.manage_products')


class VariantImageAssign(BaseMutation):
    image = graphene.Field(
        ProductImage, description='Assigned product image.')

    class Arguments:
        image_id = graphene.ID(
            required=True,
            description='ID of a product image to assign to a variant.')
        variant_id = graphene.ID(
            required=True,
            description='ID of a product variant.')

    class Meta:
        description = 'Assign an image to a product variant'

    @classmethod
    @permission_required('product.manage_products')
    def mutate(cls, root, info, image_id, variant_id):
        errors = []
        image = cls.get_node_or_error(
            info, image_id, errors, 'imageId', ProductImage)
        variant = cls.get_node_or_error(
            info, variant_id, errors, 'variantId', ProductVariant)
        if image and variant:
            # check if the given image and variant can be matched together
            image_belongs_to_product = variant.product.images.filter(
                pk=image.pk).first()
            if image_belongs_to_product:
                image.variant_images.create(variant=variant)
            else:
                cls.add_error(
                    errors, 'imageId', 'Image must be for this product')
        return VariantImageAssign(image=image, errors=errors)


class VariantImageUnassign(BaseMutation):
    class Arguments:
        image_id = graphene.ID(
            required=True,
            description='ID of a product image to unassign from a variant.')
        variant_id = graphene.ID(
            required=True, description='ID of a product variant.')

    image = graphene.Field(
        ProductImage, description='Unassigned product image.')

    class Meta:
        description = 'Unassign an image from a product variant'

    @classmethod
    @permission_required('product.manage_products')
    def mutate(cls, root, info, image_id, variant_id):
        errors = []
        image = cls.get_node_or_error(
            info, image_id, errors, 'imageId', ProductImage)
        variant = cls.get_node_or_error(
            info, variant_id, errors, 'variantId', ProductVariant)
        if image and variant:
            try:
                variant_image = models.VariantImage.objects.get(
                    image=image, variant=variant)
            except models.VariantImage.DoesNotExist:
                cls.add_error(
                    errors, 'imageId',
                    'Image is not assigned to this variant.')
            else:
                variant_image.delete()
        return VariantImageUnassign(image=image, errors=errors)
