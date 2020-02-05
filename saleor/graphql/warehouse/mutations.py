import graphene
from django.core.exceptions import ValidationError

from ...core.permissions import ProductPermissions
from ...warehouse import models
from ...warehouse.error_codes import WarehouseErrorCode
from ...warehouse.validation import validate_warehouse_count  # type: ignore
from ..account.i18n import I18nMixin
from ..core.mutations import ModelBulkDeleteMutation, ModelDeleteMutation, ModelMutation
from ..core.types.common import StockError, WarehouseError
from ..core.utils import validate_slug_and_generate_if_needed
from ..shipping.types import ShippingZone
from .types import StockInput, Warehouse, WarehouseCreateInput, WarehouseUpdateInput

ADDRESS_FIELDS = [
    "street_address_1",
    "street_address_2",
    "city",
    "city_area",
    "postal_code",
    "country",
    "country_area",
    "phone",
]


class WarehouseMixin:
    @classmethod
    def clean_input(cls, info, instance, data, input_cls=None):
        cleaned_input = super().clean_input(info, instance, data)
        try:
            cleaned_input = validate_slug_and_generate_if_needed(
                instance, "name", cleaned_input
            )
        except ValidationError as error:
            error.code = WarehouseErrorCode.REQUIRED.value
            raise ValidationError({"slug": error})
        shipping_zones = cleaned_input.get("shipping_zones", [])
        if not validate_warehouse_count(shipping_zones, instance):
            msg = "Shipping zone can be assigned only to one warehouse."
            raise ValidationError(
                {"shipping_zones": msg}, code=WarehouseErrorCode.INVALID
            )
        return cleaned_input

    @classmethod
    def construct_instance(cls, instance, cleaned_data):
        cleaned_data["address"] = cls.prepare_address(cleaned_data, instance)
        return super().construct_instance(instance, cleaned_data)


class WarehouseCreate(WarehouseMixin, ModelMutation, I18nMixin):
    class Arguments:
        input = WarehouseCreateInput(
            required=True, description="Fields required to create warehouse."
        )

    class Meta:
        description = "Creates new warehouse."
        model = models.Warehouse
        permissions = (ProductPermissions.MANAGE_PRODUCTS,)
        error_type_class = WarehouseError
        error_type_field = "warehouse_errors"

    @classmethod
    def prepare_address(cls, cleaned_data, *args):
        address_form = cls.validate_address_form(cleaned_data["address"])
        return address_form.save()


class WarehouseShippingZoneAssign(WarehouseMixin, ModelMutation, I18nMixin):
    warehouse = graphene.Field(
        Warehouse, description="A warehouse to add shipping zone."
    )

    class Meta:
        model = models.Warehouse
        permissions = (ProductPermissions.MANAGE_PRODUCTS,)
        description = "Add shipping zone to given warehouse."
        error_type_class = WarehouseError
        error_type_field = "warehouse_errors"

    class Arguments:
        id = graphene.ID(description="ID of a warehouse to update.", required=True)
        shipping_zone_ids = graphene.List(
            graphene.NonNull(graphene.ID),
            required=True,
            description="List of shipping zone IDs.",
        )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        warehouse = cls.get_node_or_error(info, data.get("id"), only_type=Warehouse)
        shipping_zones = cls.get_nodes_or_error(
            data.get("shipping_zone_ids"), "shipping_zone_id", only_type=ShippingZone
        )
        warehouse.shipping_zones.add(*shipping_zones)
        return WarehouseShippingZoneAssign(warehouse=warehouse)


class WarehouseShippingZoneUnassign(WarehouseMixin, ModelMutation, I18nMixin):
    warehouse = graphene.Field(
        Warehouse, description="A warehouse to add shipping zone."
    )

    class Meta:
        model = models.Warehouse
        permissions = (ProductPermissions.MANAGE_PRODUCTS,)
        description = "Remove shipping zone from given warehouse."
        error_type_class = WarehouseError
        error_type_field = "warehouse_errors"

    class Arguments:
        id = graphene.ID(description="ID of a warehouse to update.", required=True)
        shipping_zone_ids = graphene.List(
            graphene.NonNull(graphene.ID),
            required=True,
            description="List of shipping zone IDs.",
        )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        warehouse = cls.get_node_or_error(info, data.get("id"), only_type=Warehouse)
        shipping_zones = cls.get_nodes_or_error(
            data.get("shipping_zone_ids"), "shipping_zone_id", only_type=ShippingZone
        )
        warehouse.shipping_zones.remove(*shipping_zones)
        return WarehouseShippingZoneAssign(warehouse=warehouse)


class WarehouseUpdate(WarehouseMixin, ModelMutation, I18nMixin):
    class Meta:
        model = models.Warehouse
        permissions = (ProductPermissions.MANAGE_PRODUCTS,)
        description = "Updates given warehouse."
        error_type_class = WarehouseError
        error_type_field = "warehouse_errors"

    class Arguments:
        id = graphene.ID(description="ID of a warehouse to update.", required=True)
        input = WarehouseUpdateInput(
            required=True, description="Fields required to update warehouse."
        )

    @classmethod
    def prepare_address(cls, cleaned_data, instance):
        address_data = cleaned_data.get("address")
        address = instance.address
        if address_data is None:
            return address
        address_form = cls.validate_address_form(address_data, instance=address)
        return address_form.save()


class WarehouseDelete(ModelDeleteMutation):
    class Meta:
        model = models.Warehouse
        permissions = (ProductPermissions.MANAGE_PRODUCTS,)
        description = "Deletes selected warehouse."
        error_type_class = WarehouseError
        error_type_field = "warehouse_errors"

    class Arguments:
        id = graphene.ID(description="ID of a warehouse to delete.", required=True)


class StockCreate(ModelMutation):
    class Arguments:
        input = StockInput(
            required=True, description="Fields required to create stock."
        )

    class Meta:
        description = "Creates new stock."
        model = models.Stock
        permissions = (ProductPermissions.MANAGE_PRODUCTS,)
        error_type_class = StockError
        error_type_field = "stock_errors"


class StockUpdate(ModelMutation):
    class Arguments:
        input = StockInput(
            required=True, description="Fields required to update stock."
        )
        id = graphene.ID(required=True, description="ID of stock to update.")

    class Meta:
        model = models.Stock
        permissions = (ProductPermissions.MANAGE_PRODUCTS,)
        description = "Update given stock."
        error_type_class = StockError
        error_type_field = "stock_error"


class StockDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(required=True, description="ID of stock to delete.")

    class Meta:
        model = models.Stock
        permissions = (ProductPermissions.MANAGE_PRODUCTS,)
        description = "Deletes selected stock."
        erorr_type_class = StockError
        error_type_field = "stock_error"


class StockBulkDelete(ModelBulkDeleteMutation):
    class Arguments:
        ids = graphene.List(graphene.ID, required=True)

    class Meta:
        model = models.Stock
        permissions = (ProductPermissions.MANAGE_PRODUCTS,)
        description = "Deletes stocks in bulk"
        error_type_class = StockError
        error_type_field = "stock_error"
