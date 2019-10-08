import graphene
from django.core.exceptions import ValidationError

from ...dashboard.shipping.forms import default_shipping_zone_exists
from ...shipping import models
from ...shipping.error_codes import ShippingErrorCode
from ..core.mutations import BaseMutation, ModelDeleteMutation, ModelMutation
from ..core.scalars import Decimal, WeightScalar
from ..core.types.common import ShippingError
from .enums import ShippingMethodTypeEnum
from .types import ShippingMethod, ShippingZone


class ShippingPriceInput(graphene.InputObjectType):
    name = graphene.String(description="Name of the shipping method.")
    price = Decimal(description="Shipping price of the shipping method.")
    minimum_order_price = Decimal(
        description="Minimum order price to use this shipping method."
    )
    maximum_order_price = Decimal(
        description="Maximum order price to use this shipping method."
    )
    minimum_order_weight = WeightScalar(
        description="Minimum order weight to use this shipping method."
    )
    maximum_order_weight = WeightScalar(
        description="Maximum order weight to use this shipping method."
    )
    type = ShippingMethodTypeEnum(description="Shipping type: price or weight based.")
    shipping_zone = graphene.ID(
        description="Shipping zone this method belongs to.", name="shippingZone"
    )


class ShippingZoneInput(graphene.InputObjectType):
    name = graphene.String(
        description="Shipping zone's name. Visible only to the staff."
    )
    countries = graphene.List(
        graphene.String, description="List of countries in this shipping zone."
    )
    default = graphene.Boolean(
        description=(
            "Default shipping zone will be used for countries not covered by other "
            "zones."
        )
    )


class ShippingZoneMixin:
    @classmethod
    def clean_input(cls, info, instance, data):
        cleaned_input = super().clean_input(info, instance, data)
        default = cleaned_input.get("default")
        if default:
            if default_shipping_zone_exists(instance.pk):
                raise ValidationError(
                    {
                        "default": ValidationError(
                            "Default shipping zone already exists.",
                            code=ShippingErrorCode.ALREADY_EXISTS,
                        )
                    }
                )
            elif cleaned_input.get("countries"):
                cleaned_input["countries"] = []
        else:
            cleaned_input["default"] = False
        return cleaned_input


class ShippingZoneCreate(ShippingZoneMixin, ModelMutation):
    shipping_zone = graphene.Field(ShippingZone, description="Created shipping zone.")

    class Arguments:
        input = ShippingZoneInput(
            description="Fields required to create a shipping zone.", required=True
        )

    class Meta:
        description = "Creates a new shipping zone."
        model = models.ShippingZone
        permissions = ("shipping.manage_shipping",)
        error_type_class = ShippingError
        error_type_field = "shipping_errors"


class ShippingZoneUpdate(ShippingZoneMixin, ModelMutation):
    shipping_zone = graphene.Field(ShippingZone, description="Updated shipping zone.")

    class Arguments:
        id = graphene.ID(description="ID of a shipping zone to update.", required=True)
        input = ShippingZoneInput(
            description="Fields required to update a shipping zone.", required=True
        )

    class Meta:
        description = "Updates a new shipping zone."
        model = models.ShippingZone
        permissions = ("shipping.manage_shipping",)
        error_type_class = ShippingError
        error_type_field = "shipping_errors"


class ShippingZoneDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a shipping zone to delete.")

    class Meta:
        description = "Deletes a shipping zone."
        model = models.ShippingZone
        permissions = ("shipping.manage_shipping",)
        error_type_class = ShippingError
        error_type_field = "shipping_errors"


class ShippingPriceMixin:
    @classmethod
    def clean_input(cls, info, instance, data):
        cleaned_input = super().clean_input(info, instance, data)

        # Rename the price field to price_amount (the model's)
        price_amount = cleaned_input.pop("price", None)
        if price_amount is not None:
            cleaned_input["price_amount"] = price_amount

        cleaned_type = cleaned_input.get("type")
        if cleaned_type:
            if cleaned_type == ShippingMethodTypeEnum.PRICE.value:
                min_price = cleaned_input.pop("minimum_order_price", None)
                max_price = cleaned_input.pop("maximum_order_price", None)

                if min_price is not None:
                    cleaned_input["minimum_order_price_amount"] = min_price

                if max_price is not None:
                    cleaned_input["maximum_order_price_amount"] = max_price

                if (
                    min_price is not None
                    and max_price is not None
                    and max_price <= min_price
                ):
                    raise ValidationError(
                        {
                            "maximum_order_price": ValidationError(
                                (
                                    "Maximum order price should be larger than "
                                    "the minimum order price."
                                ),
                                code=ShippingErrorCode.MAX_LESS_THAN_MIN,
                            )
                        }
                    )
            else:
                min_weight = cleaned_input.get("minimum_order_weight")
                max_weight = cleaned_input.get("maximum_order_weight")
                if (
                    min_weight is not None
                    and max_weight is not None
                    and max_weight <= min_weight
                ):
                    raise ValidationError(
                        {
                            "maximum_order_weight": ValidationError(
                                (
                                    "Maximum order weight should be larger than the "
                                    "minimum order weight."
                                ),
                                code=ShippingErrorCode.MAX_LESS_THAN_MIN,
                            )
                        }
                    )
        return cleaned_input


class ShippingPriceCreate(ShippingPriceMixin, ModelMutation):
    shipping_zone = graphene.Field(
        ShippingZone,
        description="A shipping zone to which the shipping method belongs.",
    )

    class Arguments:
        input = ShippingPriceInput(
            description="Fields required to create a shipping price.", required=True
        )

    class Meta:
        description = "Creates a new shipping price."
        model = models.ShippingMethod
        permissions = ("shipping.manage_shipping",)
        error_type_class = ShippingError
        error_type_field = "shipping_errors"

    @classmethod
    def success_response(cls, instance):
        response = super().success_response(instance)
        response.shipping_zone = instance.shipping_zone
        return response


class ShippingPriceUpdate(ShippingPriceMixin, ModelMutation):
    shipping_zone = graphene.Field(
        ShippingZone,
        description="A shipping zone to which the shipping method belongs.",
    )

    class Arguments:
        id = graphene.ID(description="ID of a shipping price to update.", required=True)
        input = ShippingPriceInput(
            description="Fields required to update a shipping price.", required=True
        )

    class Meta:
        description = "Updates a new shipping price."
        model = models.ShippingMethod
        permissions = ("shipping.manage_shipping",)
        error_type_class = ShippingError
        error_type_field = "shipping_errors"

    @classmethod
    def success_response(cls, instance):
        response = super().success_response(instance)
        response.shipping_zone = instance.shipping_zone
        return response


class ShippingPriceDelete(BaseMutation):
    shipping_method = graphene.Field(
        ShippingMethod, description="A shipping method to delete."
    )
    shipping_zone = graphene.Field(
        ShippingZone,
        description="A shipping zone to which the shipping method belongs.",
    )

    class Arguments:
        id = graphene.ID(required=True, description="ID of a shipping price to delete.")

    class Meta:
        description = "Deletes a shipping price."
        permissions = ("shipping.manage_shipping",)
        error_type_class = ShippingError
        error_type_field = "shipping_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        shipping_method = cls.get_node_or_error(
            info, data.get("id"), only_type=ShippingMethod
        )
        shipping_method_id = shipping_method.id
        shipping_zone = shipping_method.shipping_zone
        shipping_method.delete()
        shipping_method.id = shipping_method_id
        return ShippingPriceDelete(
            shipping_method=shipping_method, shipping_zone=shipping_zone
        )
