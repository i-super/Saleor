import graphene
from graphene.types import InputObjectType

from ....graphql.product.types import Category, ProductType
from ....graphql.utils import get_node
from ....product import models
from ...category.forms import CategoryForm
from ..mutations import (
    BaseMutation, ModelDeleteMutation, ModelFormMutation,
    ModelFormUpdateMutation, StaffMemberRequiredMutation)
from ..utils import get_attributes_dict_from_list
from .forms import ProductForm


class CategoryCreateMutation(StaffMemberRequiredMutation, ModelFormMutation):
    class Arguments:
        parent_id = graphene.ID()

    class Meta:
        form_class = CategoryForm

    @classmethod
    def get_form_kwargs(cls, root, info, **input):
        parent_id = input.pop('parent_id', None)
        kwargs = super().get_form_kwargs(root, info, **input)
        if parent_id:
            parent = get_node(info, parent_id, only_type=Category)
        else:
            parent = None
        kwargs['parent_pk'] = parent.pk if parent else None
        return kwargs


class CategoryUpdateMutation(
        StaffMemberRequiredMutation, ModelFormUpdateMutation):
    class Meta:
        form_class = CategoryForm

    @classmethod
    def get_form_kwargs(cls, root, info, **input):
        kwargs = super().get_form_kwargs(root, info, **input)
        kwargs['parent_pk'] = kwargs['instance'].parent_id
        return kwargs


class CategoryDelete(StaffMemberRequiredMutation, ModelDeleteMutation):
    class Meta:
        model = models.Category


class AttributeValueInput(InputObjectType):
    slug = graphene.String(required=True)
    value = graphene.String(required=True)


class BaseProductMutateMixin(BaseMutation):
    @classmethod
    def mutate(cls, root, info, *args, **kwargs):
        form_kwargs = cls.get_form_kwargs(root, info, **kwargs)
        attributes = form_kwargs.get('data').pop('attributes', None)
        if attributes:
            form = cls._meta.form_class(**form_kwargs)
            if form.is_valid():
                attr_slug_id = dict(
                    form.instance.product_type.product_attributes.values_list(
                        'slug','id'))
                form.instance.attributes = get_attributes_dict_from_list(
                    attributes=attributes, attr_slug_id=attr_slug_id)
                instance = form.save()
                kwargs = {cls._meta.return_field_name: instance}
                return cls(errors=[], **kwargs)
        return super().mutate(root, info, *args, **kwargs)


class ProductCreateMutation(BaseProductMutateMixin,
                            StaffMemberRequiredMutation, ModelFormMutation):
    class Arguments:
        product_type_id = graphene.ID()
        category_id = graphene.ID()
        attributes = graphene.Argument(graphene.List(AttributeValueInput))

    class Meta:
        form_class = ProductForm
        # Exclude from input form fields
        # that are being overwritten by arguments
        exclude = ['product_type', 'category', 'attributes']

    @classmethod
    def get_form_kwargs(cls, root, info, **input):
        product_type_id = input.pop('product_type_id', None)
        category_id = input.pop('category_id', None)
        product_type = get_node(info, product_type_id, only_type=ProductType)
        category = get_node(info, category_id, only_type=Category)
        kwargs = super().get_form_kwargs(root, info, **input)
        kwargs['data']['product_type'] = product_type.id
        kwargs['data']['category'] = category.id
        return kwargs


class ProductDeleteMutation(StaffMemberRequiredMutation, ModelDeleteMutation):

    class Meta:
        model = models.Product


class ProductUpdateMutation(BaseProductMutateMixin,
                            StaffMemberRequiredMutation,
                            ModelFormUpdateMutation):
    class Arguments:
        attributes = graphene.Argument(graphene.List(AttributeValueInput))
        category_id = graphene.ID()

    class Meta:
        form_class = ProductForm
        # Exclude from input form fields
        # that are being overwritten by arguments
        exclude = ['product_type', 'category', 'attributes']

    @classmethod
    def get_form_kwargs(cls, root, info, **input):
        kwargs = super().get_form_kwargs(root, info, **input)
        instance = kwargs.get('instance')
        kwargs['data']['product_type'] = instance.product_type.id
        # Use provided category or existing one
        category_id = input.pop('category_id', None)
        if category_id:
            category = get_node(info, category_id, only_type=Category)
            kwargs['data']['category'] = category.id
        else:
            kwargs['data']['category'] = instance.category.id
        return kwargs
