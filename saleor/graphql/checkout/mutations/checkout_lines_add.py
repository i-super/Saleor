import graphene

from ....checkout.error_codes import CheckoutErrorCode
from ....checkout.fetch import (
    fetch_checkout_info,
    fetch_checkout_lines,
    update_delivery_method_lists_for_checkout_info,
)
from ....checkout.utils import add_variants_to_checkout, recalculate_checkout_discount
from ....warehouse.reservations import get_reservation_length, is_reservation_enabled
from ...core.descriptions import DEPRECATED_IN_3X_INPUT
from ...core.mutations import BaseMutation
from ...core.scalars import UUID
from ...core.types.common import CheckoutError
from ...core.validators import (
    validate_one_of_args_is_in_mutation,
    validate_variants_available_in_channel,
)
from ...product.types import ProductVariant
from ..types import Checkout
from .checkout_create import CheckoutLineInput
from .utils import (
    check_lines_quantity,
    get_checkout_by_token,
    group_quantity_by_variants,
    update_checkout_shipping_method_if_invalid,
    validate_variants_are_published,
    validate_variants_available_for_purchase,
)


class CheckoutLinesAdd(BaseMutation):
    checkout = graphene.Field(Checkout, description="An updated checkout.")

    class Arguments:
        checkout_id = graphene.ID(
            description=(
                f"The ID of the checkout. {DEPRECATED_IN_3X_INPUT} Use token instead."
            ),
            required=False,
        )
        token = UUID(description="Checkout token.", required=False)
        lines = graphene.List(
            CheckoutLineInput,
            required=True,
            description=(
                "A list of checkout lines, each containing information about "
                "an item in the checkout."
            ),
        )

    class Meta:
        description = (
            "Adds a checkout line to the existing checkout."
            "If line was already in checkout, its quantity will be increased."
        )
        error_type_class = CheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def validate_checkout_lines(
        cls,
        info,
        variants,
        quantities,
        country,
        channel_slug,
        lines=None,
    ):
        check_lines_quantity(
            variants,
            quantities,
            country,
            channel_slug,
            info.context.site.settings.limit_quantity_per_checkout,
            existing_lines=lines,
            check_reservations=is_reservation_enabled(info.context.site.settings),
        )

    @classmethod
    def clean_input(
        cls,
        info,
        checkout,
        variants,
        quantities,
        checkout_info,
        lines,
        manager,
        discounts,
        replace,
    ):
        channel_slug = checkout_info.channel.slug

        cls.validate_checkout_lines(
            info,
            variants,
            quantities,
            checkout.get_country(),
            channel_slug,
            lines=lines,
        )

        variants_ids_to_validate = {
            variant.id
            for variant, quantity in zip(variants, quantities)
            if quantity != 0
        }

        # validate variant only when line quantity is bigger than 0
        if variants_ids_to_validate:
            validate_variants_available_for_purchase(
                variants_ids_to_validate, checkout.channel_id
            )
            validate_variants_available_in_channel(
                variants_ids_to_validate,
                checkout.channel_id,
                CheckoutErrorCode.UNAVAILABLE_VARIANT_IN_CHANNEL,
            )
            validate_variants_are_published(
                variants_ids_to_validate, checkout.channel_id
            )

        if variants and quantities:
            checkout = add_variants_to_checkout(
                checkout,
                variants,
                quantities,
                channel_slug,
                replace=replace,
                replace_reservations=True,
                reservation_length=get_reservation_length(info.context),
            )

        lines, _ = fetch_checkout_lines(checkout)
        shipping_channel_listings = checkout.channel.shipping_method_listings.all()
        update_delivery_method_lists_for_checkout_info(
            checkout_info,
            checkout_info.checkout.shipping_method,
            checkout_info.checkout.collection_point,
            checkout_info.shipping_address,
            lines,
            discounts,
            manager,
            shipping_channel_listings,
        )
        return lines

    @classmethod
    def perform_mutation(
        cls, _root, info, lines, checkout_id=None, token=None, replace=False
    ):
        # DEPRECATED
        validate_one_of_args_is_in_mutation(
            CheckoutErrorCode, "checkout_id", checkout_id, "token", token
        )

        if token:
            checkout = get_checkout_by_token(token)
        # DEPRECATED
        else:
            checkout = cls.get_node_or_error(
                info, checkout_id or token, only_type=Checkout, field="checkout_id"
            )

        discounts = info.context.discounts
        manager = info.context.plugins

        variant_ids = [line.get("variant_id") for line in lines]
        variants = cls.get_nodes_or_error(variant_ids, "variant_id", ProductVariant)
        input_quantities = group_quantity_by_variants(lines)

        shipping_channel_listings = checkout.channel.shipping_method_listings.all()
        checkout_info = fetch_checkout_info(
            checkout, [], discounts, manager, shipping_channel_listings
        )

        lines, _ = fetch_checkout_lines(checkout)
        lines = cls.clean_input(
            info,
            checkout,
            variants,
            input_quantities,
            checkout_info,
            lines,
            manager,
            discounts,
            replace,
        )
        update_checkout_shipping_method_if_invalid(checkout_info, lines)
        recalculate_checkout_discount(
            manager, checkout_info, lines, info.context.discounts
        )
        manager.checkout_updated(checkout)
        return CheckoutLinesAdd(checkout=checkout)
