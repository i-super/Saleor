import graphene
import graphene_django_optimizer as gql_optimizer
from graphql_jwt.exceptions import PermissionDenied

from ...checkout import calculations, models
from ...checkout.utils import get_valid_shipping_methods_for_checkout
from ...core.permissions import AccountPermissions, CheckoutPermissions
from ...core.taxes import display_gross_prices, zero_taxed_money
from ...plugins.manager import get_plugins_manager
from ..core.connection import CountableDjangoObjectType
from ..core.types.money import TaxedMoney
from ..decorators import permission_required
from ..giftcard.types import GiftCard
from ..meta.deprecated.resolvers import resolve_meta, resolve_private_meta
from ..meta.types import ObjectWithMetadata
from ..shipping.types import ShippingMethod


class GatewayConfigLine(graphene.ObjectType):
    field = graphene.String(required=True, description="Gateway config key.")
    value = graphene.String(description="Gateway config value for key.")

    class Meta:
        description = "Payment gateway client configuration key and value pair."


class PaymentGateway(graphene.ObjectType):
    name = graphene.String(required=True, description="Payment gateway name.")
    config = graphene.List(
        graphene.NonNull(GatewayConfigLine),
        required=True,
        description="Payment gateway client configuration.",
    )

    class Meta:
        description = (
            "Available payment gateway backend with configuration "
            "necessary to setup client."
        )


class CheckoutLine(CountableDjangoObjectType):
    total_price = graphene.Field(
        TaxedMoney,
        description="The sum of the checkout line price, taxes and discounts.",
    )
    requires_shipping = graphene.Boolean(
        description="Indicates whether the item need to be delivered."
    )

    class Meta:
        only_fields = ["id", "quantity", "variant"]
        description = "Represents an item in the checkout."
        interfaces = [graphene.relay.Node]
        model = models.CheckoutLine
        filter_fields = ["id"]

    @staticmethod
    def resolve_total_price(self, info):
        return info.context.plugins.calculate_checkout_line_total(
            checkout_line=self, discounts=info.context.discounts
        )

    @staticmethod
    def resolve_requires_shipping(root: models.CheckoutLine, *_args):
        return root.is_shipping_required()


class Checkout(CountableDjangoObjectType):
    available_shipping_methods = graphene.List(
        ShippingMethod,
        required=True,
        description="Shipping methods that can be used with this order.",
    )
    available_payment_gateways = graphene.List(
        PaymentGateway, description="List of available payment gateways.", required=True
    )
    email = graphene.String(description="Email of a customer.", required=True)
    gift_cards = gql_optimizer.field(
        graphene.List(
            GiftCard, description="List of gift cards associated with this checkout."
        ),
        model_field="gift_cards",
    )
    is_shipping_required = graphene.Boolean(
        description="Returns True, if checkout requires shipping.", required=True
    )
    lines = gql_optimizer.field(
        graphene.List(
            CheckoutLine,
            description=(
                "A list of checkout lines, each containing information about "
                "an item in the checkout."
            ),
        ),
        model_field="lines",
    )
    shipping_price = graphene.Field(
        TaxedMoney,
        description="The price of the shipping, with all the taxes included.",
    )
    subtotal_price = graphene.Field(
        TaxedMoney,
        description="The price of the checkout before shipping, with taxes included.",
    )
    total_price = graphene.Field(
        TaxedMoney,
        description=(
            "The sum of the the checkout line prices, with all the taxes,"
            "shipping costs, and discounts included."
        ),
    )

    class Meta:
        only_fields = [
            "billing_address",
            "created",
            "discount_name",
            "gift_cards",
            "is_shipping_required",
            "last_change",
            "note",
            "quantity",
            "shipping_address",
            "shipping_method",
            "token",
            "translated_discount_name",
            "user",
            "voucher_code",
            "discount",
        ]
        description = "Checkout object."
        model = models.Checkout
        interfaces = [graphene.relay.Node, ObjectWithMetadata]
        filter_fields = ["token"]

    @staticmethod
    def resolve_user(root: models.Checkout, info):
        user = info.context.user
        if user == root.user or user.has_perm(AccountPermissions.MANAGE_USERS):
            return root.user
        raise PermissionDenied()

    @staticmethod
    def resolve_email(root: models.Checkout, info):
        return root.get_customer_email()

    @staticmethod
    def resolve_total_price(root: models.Checkout, info):
        taxed_total = (
            calculations.checkout_total(checkout=root, discounts=info.context.discounts)
            - root.get_total_gift_cards_balance()
        )
        return max(taxed_total, zero_taxed_money())

    @staticmethod
    def resolve_subtotal_price(root: models.Checkout, info):
        return calculations.checkout_subtotal(
            checkout=root, discounts=info.context.discounts
        )

    @staticmethod
    def resolve_shipping_price(root: models.Checkout, info):
        return calculations.checkout_shipping_price(
            checkout=root, discounts=info.context.discounts
        )

    @staticmethod
    def resolve_lines(root: models.Checkout, *_args):
        return root.lines.prefetch_related("variant")

    @staticmethod
    def resolve_available_shipping_methods(root: models.Checkout, info):
        available = get_valid_shipping_methods_for_checkout(
            root, info.context.discounts
        )
        if available is None:
            return []

        manager = get_plugins_manager()
        display_gross = display_gross_prices()
        for shipping_method in available:
            # ignore mypy checking because it is checked in
            # get_valid_shipping_methods_for_checkout
            taxed_price = manager.apply_taxes_to_shipping(
                shipping_method.price, root.shipping_address  # type: ignore
            )
            if display_gross:
                shipping_method.price = taxed_price.gross
            else:
                shipping_method.price = taxed_price.net
        return available

    @staticmethod
    def resolve_available_payment_gateways(_: models.Checkout, _info):
        return [gtw for gtw in get_plugins_manager().list_payment_gateways()]

    @staticmethod
    def resolve_gift_cards(root: models.Checkout, _info):
        return root.gift_cards.all()

    @staticmethod
    def resolve_is_shipping_required(root: models.Checkout, _info):
        return root.is_shipping_required()

    @staticmethod
    @permission_required(CheckoutPermissions.MANAGE_CHECKOUTS)
    def resolve_private_meta(root: models.Checkout, _info):
        return resolve_private_meta(root, _info)

    @staticmethod
    def resolve_meta(root: models.Checkout, _info):
        return resolve_meta(root, _info)
