import graphene

from ...discount import models
from ...discount.utils import generate_voucher_code
from ..core.mutations import BaseMutation, ModelDeleteMutation, ModelMutation
from ..core.scalars import Decimal
from ..product.types import Category, Collection, Product
from .enums import DiscountValueTypeEnum, VoucherTypeEnum
from .types import Sale, Voucher


class CatalogueInput(graphene.InputObjectType):
    products = graphene.List(
        graphene.ID,
        description='Products related to the discount.',
        name='products')
    categories = graphene.List(
        graphene.ID,
        description='Categories related to the discount.',
        name='categories')
    collections = graphene.List(
        graphene.ID,
        description='Collections related to the discount.',
        name='collections')


class BaseDiscountCatalogueMutation(BaseMutation):
    class Meta:
        abstract = True

    @classmethod
    def add_catalogues_to_node(cls, node, input, errors):
        products = input.get('products', [])
        if products:
            products = cls.get_nodes_or_error(
                products, errors, 'products', only_type=Product)
            node.products.add(*products)
        categories = input.get('categories', [])
        if categories:
            categories = cls.get_nodes_or_error(
                categories, errors, 'categories', only_type=Category)
            node.categories.add(*categories)
        collections = input.get('collections', [])
        if collections:
            collections = cls.get_nodes_or_error(
                collections, errors, 'collections', only_type=Collection)
            node.collections.add(*collections)

    @classmethod
    def remove_catalogues_from_node(cls, node, input, errors):
        products = input.get('products', [])
        if products:
            products = cls.get_nodes_or_error(
                products, errors, 'products', only_type=Product)
            node.products.remove(*products)
        categories = input.get('categories', [])
        if categories:
            categories = cls.get_nodes_or_error(
                categories, errors, 'categories', only_type=Category)
            node.categories.remove(*categories)
        collections = input.get('collections', [])
        if collections:
            collections = cls.get_nodes_or_error(
                collections, errors, 'collections', only_type=Collection)
            node.collections.remove(*collections)


class VoucherInput(graphene.InputObjectType):
    type = VoucherTypeEnum(
        description='Voucher type: product, category shipping or value.')
    name = graphene.String(description='Voucher name.')
    code = graphene.String(decription='Code to use the voucher.')
    start_date = graphene.types.datetime.Date(
        description='Start date of the voucher in ISO 8601 format.')
    end_date = graphene.types.datetime.Date(
        description='End date of the voucher in ISO 8601 format.')
    discount_value_type = DiscountValueTypeEnum(
        description='Choices: fixed or percentage.')
    discount_value = Decimal(description='Value of the voucher.')
    products = graphene.List(
        graphene.ID,
        description='Products discounted by the voucher.',
        name='products')
    collections = graphene.List(
        graphene.ID,
        description='Collections discounted by the voucher.',
        name='collections')
    categories = graphene.List(
        graphene.ID,
        description='Categories discounted by the voucher.',
        name='categories')
    min_amount_spent = Decimal(
        description='Min purchase amount required to apply the voucher.')
    countries = graphene.List(
        graphene.String,
        description='Country codes that can be used with the shipping voucher')


class VoucherCreate(ModelMutation):
    class Arguments:
        input = VoucherInput(
            required=True, description='Fields required to create a voucher.')

    class Meta:
        description = 'Creates a new voucher.'
        model = models.Voucher

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('discount.manage_discounts')

    @classmethod
    def clean_input(cls, info, instance, input, errors):
        code = input.get('code', None)
        if code == '':
            input['code'] = generate_voucher_code()
        cleaned_input = super().clean_input(info, instance, input, errors)
        return cleaned_input


class VoucherUpdate(VoucherCreate):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of a voucher to update.')
        input = VoucherInput(
            required=True, description='Fields required to update a voucher.')

    class Meta:
        description = 'Updates a voucher.'
        model = models.Voucher


class VoucherDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(
            required=True, description='ID of a voucher to delete.')

    class Meta:
        description = 'Deletes a voucher.'
        model = models.Voucher

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('discount.manage_discounts')


class VoucherBaseCatalogueMutation(BaseDiscountCatalogueMutation):
    voucher = graphene.Field(
        Voucher,
        description=('Voucher of which catalogue IDs will be modified.'))

    class Arguments:
        id = graphene.ID(required=True, description='ID of a voucher.')
        input = CatalogueInput(
            required=True,
            description=(
                'Fields required to modify catalogue IDs of voucher.'))

    class Meta:
        abstract = True


class VoucherAddCatalogues(VoucherBaseCatalogueMutation):
    class Meta:
        description = 'Adds products, categories, collections to a voucher.'

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('discount.manage_discounts')

    @classmethod
    def perform_mutation(cls, root, info, id, input):
        errors = []
        voucher = cls.get_node_or_error(
            info, id, errors, 'voucherId', only_type=Voucher)

        cls.add_catalogues_to_node(voucher, input, errors)
        return VoucherAddCatalogues(voucher=voucher, errors=errors)


class VoucherRemoveCatalogues(VoucherBaseCatalogueMutation):
    class Meta:
        description = (
            'Removes products, categories, collections from a voucher.')

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('discount.manage_discounts')

    @classmethod
    def perform_mutation(cls, root, info, id, input):
        errors = []
        voucher = cls.get_node_or_error(
            info, id, errors, 'voucherId', only_type=Voucher)

        cls.remove_catalogues_from_node(voucher, input, errors)
        return VoucherRemoveCatalogues(voucher=voucher, errors=errors)


class SaleInput(graphene.InputObjectType):
    name = graphene.String(description='Voucher name.')
    type = DiscountValueTypeEnum(description='Fixed or percentage.')
    value = Decimal(description='Value of the voucher.')
    products = graphene.List(
        graphene.ID,
        description='Products related to the discount.',
        name='products')
    categories = graphene.List(
        graphene.ID,
        description='Categories related to the discount.',
        name='categories')
    collections = graphene.List(
        graphene.ID,
        description='Collections related to the discount.',
        name='collections')
    start_date = graphene.Date(
        description='Start date of the sale in ISO 8601 format.')
    end_date = graphene.Date(
        description='End date of the sale in ISO 8601 format.')


class SaleCreate(ModelMutation):
    class Arguments:
        input = SaleInput(
            required=True, description='Fields required to create a sale.')

    class Meta:
        description = 'Creates a new sale.'
        model = models.Sale

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('discount.manage_discounts')


class SaleUpdate(ModelMutation):
    class Arguments:
        id = graphene.ID(required=True, description='ID of a sale to update.')
        input = SaleInput(
            required=True, description='Fields required to update a sale.')

    class Meta:
        description = 'Updates a sale.'
        model = models.Sale

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('discount.manage_discounts')


class SaleDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(required=True, description='ID of a sale to delete.')

    class Meta:
        description = 'Deletes a sale.'
        model = models.Sale

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('discount.manage_discounts')


class SaleBaseCatalogueMutation(BaseDiscountCatalogueMutation):
    sale = graphene.Field(
        Sale, description=('Sale of which catalogue IDs will be modified.'))

    class Arguments:
        id = graphene.ID(required=True, description='ID of a sale.')
        input = CatalogueInput(
            required=True,
            description=('Fields required to modify catalogue IDs of sale.'))

    class Meta:
        abstract = True


class SaleAddCatalogues(SaleBaseCatalogueMutation):
    class Meta:
        description = 'Adds products, categories, collections to a voucher.'

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('discount.manage_discounts')

    @classmethod
    def perform_mutation(cls, root, info, id, input):
        errors = []
        sale = cls.get_node_or_error(
            info, id, errors, 'saleId', only_type=Sale)

        cls.add_catalogues_to_node(sale, input, errors)
        return SaleAddCatalogues(sale=sale, errors=errors)


class SaleRemoveCatalogues(SaleBaseCatalogueMutation):
    class Meta:
        description = 'Removes products, categories, collections from a sale.'

    @classmethod
    def user_is_allowed(cls, user, input):
        return user.has_perm('discount.manage_discounts')

    @classmethod
    def perform_mutation(cls, root, info, id, input):
        errors = []
        sale = cls.get_node_or_error(
            info, id, errors, 'saleId', only_type=Sale)

        cls.remove_catalogues_from_node(sale, input, errors)
        return SaleRemoveCatalogues(sale=sale, errors=errors)
