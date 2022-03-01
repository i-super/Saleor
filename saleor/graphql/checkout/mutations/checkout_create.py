from typing import TYPE_CHECKING, List, Optional, Tuple

import graphene
from django.conf import settings

from ....checkout import AddressType, models
from ....checkout.error_codes import CheckoutErrorCode
from ....checkout.utils import add_variants_to_checkout
from ....core.tracing import traced_atomic_transaction
from ....product import models as product_models
from ....warehouse.reservations import get_reservation_length, is_reservation_enabled
from ...account.i18n import I18nMixin
from ...account.types import AddressInput
from ...channel.utils import clean_channel
from ...core.descriptions import DEPRECATED_IN_3X_FIELD
from ...core.enums import LanguageCodeEnum
from ...core.mutations import ModelMutation
from ...core.types.common import CheckoutError
from ...core.validators import validate_variants_available_in_channel
from ...product.types import ProductVariant
from ..types import Checkout
from .utils import (
    check_lines_quantity,
    group_quantity_by_variants,
    validate_variants_are_published,
    validate_variants_available_for_purchase,
)

if TYPE_CHECKING:
    from ....account.models import Address


class CheckoutLineInput(graphene.InputObjectType):
    quantity = graphene.Int(required=True, description="The number of items purchased.")
    variant_id = graphene.ID(required=True, description="ID of the product variant.")


class CheckoutCreateInput(graphene.InputObjectType):
    channel = graphene.String(
        description="Slug of a channel in which to create a checkout."
    )
    lines = graphene.List(
        CheckoutLineInput,
        description=(
            "A list of checkout lines, each containing information about "
            "an item in the checkout."
        ),
        required=True,
    )
    email = graphene.String(description="The customer's email address.")
    shipping_address = AddressInput(
        description=(
            "The mailing address to where the checkout will be shipped. "
            "Note: the address will be ignored if the checkout "
            "doesn't contain shippable items."
        )
    )
    billing_address = AddressInput(description="Billing address of the customer.")
    language_code = graphene.Argument(
        LanguageCodeEnum, required=False, description="Checkout language code."
    )


class CheckoutCreate(ModelMutation, I18nMixin):
    created = graphene.Field(
        graphene.Boolean,
        description=(
            "Whether the checkout was created or the current active one was returned. "
            "Refer to checkoutLinesAdd and checkoutLinesUpdate to merge a cart "
            "with an active checkout."
        ),
        deprecation_reason=f"{DEPRECATED_IN_3X_FIELD} Always returns `true`.",
    )

    class Arguments:
        input = CheckoutCreateInput(
            required=True, description="Fields required to create checkout."
        )

    class Meta:
        description = "Create a new checkout."
        model = models.Checkout
        object_type = Checkout
        return_field_name = "checkout"
        error_type_class = CheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def clean_checkout_lines(
        cls, info, lines, country, channel
    ) -> Tuple[List[product_models.ProductVariant], List[int]]:
        variant_ids = [line["variant_id"] for line in lines]
        variants = cls.get_nodes_or_error(
            variant_ids,
            "variant_id",
            ProductVariant,
            qs=product_models.ProductVariant.objects.prefetch_related(
                "product__product_type"
            ),
        )

        quantities = group_quantity_by_variants(lines)

        variant_db_ids = {variant.id for variant in variants}
        validate_variants_available_for_purchase(variant_db_ids, channel.id)
        validate_variants_available_in_channel(
            variant_db_ids, channel.id, CheckoutErrorCode.UNAVAILABLE_VARIANT_IN_CHANNEL
        )
        validate_variants_are_published(variant_db_ids, channel.id)
        check_lines_quantity(
            variants,
            quantities,
            country,
            channel.slug,
            info.context.site.settings.limit_quantity_per_checkout,
            check_reservations=is_reservation_enabled(info.context.site.settings),
        )
        return variants, quantities

    @classmethod
    def retrieve_shipping_address(cls, user, data: dict) -> Optional["Address"]:
        if data.get("shipping_address") is not None:
            return cls.validate_address(
                data["shipping_address"], address_type=AddressType.SHIPPING
            )
        if user.is_authenticated:
            return user.default_shipping_address
        return None

    @classmethod
    def retrieve_billing_address(cls, user, data: dict) -> Optional["Address"]:
        if data.get("billing_address") is not None:
            return cls.validate_address(
                data["billing_address"], address_type=AddressType.BILLING
            )
        if user.is_authenticated:
            return user.default_billing_address
        return None

    @classmethod
    def clean_input(cls, info, instance: models.Checkout, data, input_cls=None):
        user = info.context.user
        channel = data.pop("channel")
        cleaned_input = super().clean_input(info, instance, data)

        cleaned_input["channel"] = channel
        cleaned_input["currency"] = channel.currency_code

        shipping_address = cls.retrieve_shipping_address(user, data)
        billing_address = cls.retrieve_billing_address(user, data)

        if shipping_address:
            country = shipping_address.country.code
        else:
            country = channel.default_country

        # Resolve and process the lines, retrieving the variants and quantities
        lines = data.pop("lines", None)
        if lines:
            (
                cleaned_input["variants"],
                cleaned_input["quantities"],
            ) = cls.clean_checkout_lines(
                info,
                lines,
                country,
                cleaned_input["channel"],
            )

        # Use authenticated user's email as default email
        if user.is_authenticated:
            email = data.pop("email", None)
            cleaned_input["email"] = email or user.email

        language_code = data.get("language_code", settings.LANGUAGE_CODE)
        cleaned_input["language_code"] = language_code

        cleaned_input["shipping_address"] = shipping_address
        cleaned_input["billing_address"] = billing_address
        cleaned_input["country"] = country
        return cleaned_input

    @classmethod
    @traced_atomic_transaction()
    def save(cls, info, instance: models.Checkout, cleaned_input):
        # Create the checkout object
        instance.save()

        # Set checkout country
        country = cleaned_input["country"]
        instance.set_country(country)
        # Create checkout lines
        channel = cleaned_input["channel"]
        variants = cleaned_input.get("variants")
        quantities = cleaned_input.get("quantities")
        if variants and quantities:
            add_variants_to_checkout(
                instance,
                variants,
                quantities,
                channel.slug,
                info.context.site.settings.limit_quantity_per_checkout,
                reservation_length=get_reservation_length(info.context),
            )

        # Save addresses
        shipping_address = cleaned_input.get("shipping_address")
        if shipping_address and instance.is_shipping_required():
            shipping_address.save()
            instance.shipping_address = shipping_address.get_copy()

        billing_address = cleaned_input.get("billing_address")
        if billing_address:
            billing_address.save()
            instance.billing_address = billing_address.get_copy()

        instance.save()

    @classmethod
    def get_instance(cls, info, **data):
        instance = super().get_instance(info, **data)
        user = info.context.user
        if user.is_authenticated:
            instance.user = user
        return instance

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        channel_input = data.get("input", {}).get("channel")
        channel = clean_channel(channel_input, error_class=CheckoutErrorCode)
        if channel:
            data["input"]["channel"] = channel
        response = super().perform_mutation(_root, info, **data)
        info.context.plugins.checkout_created(response.checkout)
        response.created = True
        return response
