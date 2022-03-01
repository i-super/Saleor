from typing import Optional

import graphene
from django.core.exceptions import ValidationError

from ....checkout.error_codes import CheckoutErrorCode
from ....checkout.fetch import fetch_checkout_info, fetch_checkout_lines
from ....checkout.utils import (
    delete_external_shipping_id,
    is_shipping_required,
    recalculate_checkout_discount,
    set_external_shipping_id,
)
from ....plugins.webhook.utils import APP_ID_PREFIX
from ....shipping import interface as shipping_interface
from ....shipping import models as shipping_models
from ....shipping.utils import convert_to_shipping_method_data
from ....warehouse import models as warehouse_models
from ...core.descriptions import ADDED_IN_31, PREVIEW_FEATURE
from ...core.mutations import BaseMutation
from ...core.scalars import UUID
from ...core.types.common import CheckoutError
from ...core.utils import from_global_id_or_error
from ...shipping.types import ShippingMethod
from ...warehouse.types import Warehouse
from ..types import Checkout
from .utils import ERROR_DOES_NOT_SHIP, clean_delivery_method, get_checkout_by_token


class CheckoutDeliveryMethodUpdate(BaseMutation):
    checkout = graphene.Field(Checkout, description="An updated checkout.")

    class Arguments:
        token = UUID(description="Checkout token.", required=False)
        delivery_method_id = graphene.ID(
            description="Delivery Method ID (`Warehouse` ID or `ShippingMethod` ID).",
            required=False,
        )

    class Meta:
        description = (
            f"{ADDED_IN_31} Updates the delivery method "
            f"(shipping method or pick up point) of the checkout. {PREVIEW_FEATURE}"
        )
        error_type_class = CheckoutError

    @classmethod
    def perform_on_shipping_method(
        cls, info, shipping_method_id, checkout_info, lines, checkout, manager
    ):
        shipping_method = cls.get_node_or_error(
            info,
            shipping_method_id,
            only_type=ShippingMethod,
            field="delivery_method_id",
            qs=shipping_models.ShippingMethod.objects.prefetch_related(
                "postal_code_rules"
            ),
        )

        delivery_method = convert_to_shipping_method_data(
            shipping_method,
            shipping_models.ShippingMethodChannelListing.objects.filter(
                shipping_method=shipping_method,
                channel=checkout_info.channel,
            ).first(),
        )
        cls._check_delivery_method(
            checkout_info, lines, shipping_method=delivery_method, collection_point=None
        )

        cls._update_delivery_method(
            manager,
            checkout,
            shipping_method=shipping_method,
            external_shipping_method=None,
            collection_point=None,
        )
        recalculate_checkout_discount(
            manager, checkout_info, lines, info.context.discounts
        )
        return CheckoutDeliveryMethodUpdate(checkout=checkout)

    @classmethod
    def perform_on_external_shipping_method(
        cls, info, shipping_method_id, checkout_info, lines, checkout, manager
    ):
        delivery_method = manager.get_shipping_method(
            checkout=checkout,
            channel_slug=checkout.channel.slug,
            shipping_method_id=shipping_method_id,
        )

        cls._check_delivery_method(
            checkout_info, lines, shipping_method=delivery_method, collection_point=None
        )

        cls._update_delivery_method(
            manager,
            checkout,
            shipping_method=None,
            external_shipping_method=delivery_method,
            collection_point=None,
        )
        recalculate_checkout_discount(
            manager, checkout_info, lines, info.context.discounts
        )
        return CheckoutDeliveryMethodUpdate(checkout=checkout)

    @classmethod
    def perform_on_collection_point(
        cls, info, collection_point_id, checkout_info, lines, checkout, manager
    ):
        collection_point = cls.get_node_or_error(
            info,
            collection_point_id,
            only_type=Warehouse,
            field="delivery_method_id",
            qs=warehouse_models.Warehouse.objects.select_related("address"),
        )
        cls._check_delivery_method(
            checkout_info,
            lines,
            shipping_method=None,
            collection_point=collection_point,
        )
        cls._update_delivery_method(
            manager,
            checkout,
            shipping_method=None,
            external_shipping_method=None,
            collection_point=collection_point,
        )
        return CheckoutDeliveryMethodUpdate(checkout=checkout)

    @staticmethod
    def _check_delivery_method(
        checkout_info,
        lines,
        *,
        shipping_method: Optional[shipping_interface.ShippingMethodData],
        collection_point: Optional[Warehouse]
    ) -> None:
        delivery_method = shipping_method
        error_msg = "This shipping method is not applicable."

        if collection_point is not None:
            delivery_method = collection_point
            error_msg = "This pick up point is not applicable."

        delivery_method_is_valid = clean_delivery_method(
            checkout_info=checkout_info, lines=lines, method=delivery_method
        )
        if not delivery_method_is_valid:
            raise ValidationError(
                {
                    "delivery_method_id": ValidationError(
                        error_msg,
                        code=CheckoutErrorCode.DELIVERY_METHOD_NOT_APPLICABLE.value,
                    )
                }
            )

    @staticmethod
    def _update_delivery_method(
        manager,
        checkout: Checkout,
        *,
        shipping_method: Optional[ShippingMethod],
        external_shipping_method: Optional[shipping_interface.ShippingMethodData],
        collection_point: Optional[Warehouse]
    ) -> None:
        if external_shipping_method:
            set_external_shipping_id(
                checkout=checkout, app_shipping_id=external_shipping_method.id
            )
        else:
            delete_external_shipping_id(checkout=checkout)
        checkout.shipping_method = shipping_method
        checkout.collection_point = collection_point
        checkout.save(
            update_fields=[
                "private_metadata",
                "shipping_method",
                "collection_point",
                "last_change",
            ]
        )
        manager.checkout_updated(checkout)

    @staticmethod
    def _resolve_delivery_method_type(id_) -> Optional[str]:
        if id_ is None:
            return None

        possible_types = ("Warehouse", "ShippingMethod", APP_ID_PREFIX)
        type_, id_ = from_global_id_or_error(id_)
        str_type = str(type_)

        if str_type not in possible_types:
            raise ValidationError(
                {
                    "delivery_method_id": ValidationError(
                        "ID does not belong to Warehouse or ShippingMethod",
                        code=CheckoutErrorCode.INVALID.value,
                    )
                }
            )

        return str_type

    @classmethod
    def perform_mutation(
        cls,
        _,
        info,
        token,
        delivery_method_id=None,
    ):

        checkout = get_checkout_by_token(token)

        manager = info.context.plugins
        lines, unavailable_variant_pks = fetch_checkout_lines(checkout)
        if unavailable_variant_pks:
            not_available_variants_ids = {
                graphene.Node.to_global_id("ProductVariant", pk)
                for pk in unavailable_variant_pks
            }
            raise ValidationError(
                {
                    "lines": ValidationError(
                        "Some of the checkout lines variants are unavailable.",
                        code=CheckoutErrorCode.UNAVAILABLE_VARIANT_IN_CHANNEL.value,
                        params={"variants": not_available_variants_ids},
                    )
                }
            )

        if not is_shipping_required(lines):
            raise ValidationError(
                {
                    "delivery_method": ValidationError(
                        ERROR_DOES_NOT_SHIP,
                        code=CheckoutErrorCode.SHIPPING_NOT_REQUIRED,
                    )
                }
            )
        type_name = cls._resolve_delivery_method_type(delivery_method_id)

        checkout_info = fetch_checkout_info(
            checkout, lines, info.context.discounts, manager
        )
        if type_name == "Warehouse":
            return cls.perform_on_collection_point(
                info, delivery_method_id, checkout_info, lines, checkout, manager
            )
        if type_name == "ShippingMethod":
            return cls.perform_on_shipping_method(
                info, delivery_method_id, checkout_info, lines, checkout, manager
            )
        return cls.perform_on_external_shipping_method(
            info, delivery_method_id, checkout_info, lines, checkout, manager
        )
