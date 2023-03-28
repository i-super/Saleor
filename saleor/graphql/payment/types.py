import graphene
from graphene import relay

from ...core.exceptions import PermissionDenied
from ...payment import models
from ...permission.enums import OrderPermissions
from ..account.dataloaders import UserByUserIdLoader
from ..app.dataloaders import AppByIdLoader, AppsByAppIdentifierLoader
from ..checkout.dataloaders import CheckoutByTokenLoader
from ..core.connection import CountableConnection
from ..core.descriptions import (
    ADDED_IN_31,
    ADDED_IN_34,
    ADDED_IN_36,
    ADDED_IN_313,
    PREVIEW_FEATURE,
    PREVIEW_FEATURE_DEPRECATED_IN_313_FIELD,
)
from ..core.doc_category import DOC_CATEGORY_PAYMENTS
from ..core.fields import JSONString, PermissionsField
from ..core.tracing import traced_resolver
from ..core.types import BaseObjectType, ModelObjectType, Money, NonNullList
from ..meta.permissions import public_payment_permissions
from ..meta.resolvers import resolve_metadata
from ..meta.types import MetadataItem, ObjectWithMetadata
from ..order.dataloaders import OrderByIdLoader
from ..utils import get_user_or_app_from_context
from .dataloaders import (
    TransactionByPaymentIdLoader,
    TransactionEventByTransactionIdLoader,
)
from .enums import (
    OrderAction,
    PaymentChargeStatusEnum,
    TransactionActionEnum,
    TransactionEventStatusEnum,
    TransactionEventTypeEnum,
    TransactionKindEnum,
)


class Transaction(ModelObjectType[models.Transaction]):
    id = graphene.GlobalID(required=True)
    created = graphene.DateTime(required=True)
    payment = graphene.Field(lambda: Payment, required=True)
    token = graphene.String(required=True)
    kind = TransactionKindEnum(required=True)
    is_success = graphene.Boolean(required=True)
    error = graphene.String()
    gateway_response = JSONString(required=True)
    amount = graphene.Field(Money, description="Total amount of the transaction.")

    class Meta:
        description = "An object representing a single payment."
        interfaces = [relay.Node]
        model = models.Transaction

    @staticmethod
    def resolve_created(root: models.Transaction, _info):
        return root.created_at

    @staticmethod
    def resolve_amount(root: models.Transaction, _info):
        return root.get_amount()


class CreditCard(BaseObjectType):
    brand = graphene.String(description="Card brand.", required=True)
    first_digits = graphene.String(
        description="First 4 digits of the card number.", required=False
    )
    last_digits = graphene.String(
        description="Last 4 digits of the card number.", required=True
    )
    exp_month = graphene.Int(
        description="Two-digit number representing the card’s expiration month.",
        required=False,
    )
    exp_year = graphene.Int(
        description="Four-digit number representing the card’s expiration year.",
        required=False,
    )

    class Meta:
        doc_category = DOC_CATEGORY_PAYMENTS


class PaymentSource(BaseObjectType):
    class Meta:
        description = (
            "Represents a payment source stored "
            "for user in payment gateway, such as credit card."
        )
        doc_category = DOC_CATEGORY_PAYMENTS

    gateway = graphene.String(description="Payment gateway name.", required=True)
    payment_method_id = graphene.String(description="ID of stored payment method.")
    credit_card_info = graphene.Field(
        CreditCard, description="Stored credit card details if available."
    )
    metadata = NonNullList(
        MetadataItem,
        required=True,
        description=(
            "List of public metadata items."
            + ADDED_IN_31
            + "\n\nCan be accessed without permissions."
        ),
    )


class Payment(ModelObjectType[models.Payment]):
    id = graphene.GlobalID(required=True)
    gateway = graphene.String(required=True)
    is_active = graphene.Boolean(required=True)
    created = graphene.DateTime(required=True)
    modified = graphene.DateTime(required=True)
    token = graphene.String(required=True)
    checkout = graphene.Field("saleor.graphql.checkout.types.Checkout")
    order = graphene.Field("saleor.graphql.order.types.Order")
    payment_method_type = graphene.String(required=True)
    customer_ip_address = PermissionsField(
        graphene.String,
        description="IP address of the user who created the payment.",
        permissions=[OrderPermissions.MANAGE_ORDERS],
    )
    charge_status = PaymentChargeStatusEnum(
        description="Internal payment status.", required=True
    )
    actions = PermissionsField(
        NonNullList(OrderAction),
        description=(
            "List of actions that can be performed in the current state of a payment."
        ),
        required=True,
        permissions=[
            OrderPermissions.MANAGE_ORDERS,
        ],
    )
    total = graphene.Field(Money, description="Total amount of the payment.")
    captured_amount = graphene.Field(
        Money, description="Total amount captured for this payment."
    )
    transactions = PermissionsField(
        NonNullList(Transaction),
        description="List of all transactions within this payment.",
        permissions=[
            OrderPermissions.MANAGE_ORDERS,
        ],
    )
    available_capture_amount = PermissionsField(
        Money,
        description="Maximum amount of money that can be captured.",
        permissions=[OrderPermissions.MANAGE_ORDERS],
    )
    available_refund_amount = PermissionsField(
        Money,
        description="Maximum amount of money that can be refunded.",
        permissions=[OrderPermissions.MANAGE_ORDERS],
    )
    credit_card = graphene.Field(
        CreditCard, description="The details of the card used for this payment."
    )

    class Meta:
        description = "Represents a payment of a given type."
        interfaces = [relay.Node, ObjectWithMetadata]
        model = models.Payment

    @staticmethod
    def resolve_created(root: models.Payment, _info):
        return root.created_at

    @staticmethod
    def resolve_modified(root: models.Payment, _info):
        return root.modified_at

    @staticmethod
    def resolve_customer_ip_address(root: models.Payment, _info):
        return root.customer_ip_address

    @staticmethod
    def resolve_actions(root: models.Payment, _info):
        actions = []
        if root.can_capture():
            actions.append(OrderAction.CAPTURE)
        if root.can_refund():
            actions.append(OrderAction.REFUND)
        if root.can_void():
            actions.append(OrderAction.VOID)
        return actions

    @staticmethod
    @traced_resolver
    def resolve_total(root: models.Payment, _info):
        return root.get_total()

    @staticmethod
    def resolve_captured_amount(root: models.Payment, _info):
        return root.get_captured_amount()

    @staticmethod
    def resolve_transactions(root: models.Payment, info):
        return TransactionByPaymentIdLoader(info.context).load(root.id)

    @staticmethod
    def resolve_available_refund_amount(root: models.Payment, _info):
        if not root.can_refund():
            return None
        return root.get_captured_amount()

    @staticmethod
    def resolve_available_capture_amount(root: models.Payment, _info):
        if not root.can_capture():
            return None
        return Money(amount=root.get_charge_amount(), currency=root.currency)

    @staticmethod
    def resolve_credit_card(root: models.Payment, _info):
        data = {
            "brand": root.cc_brand,
            "exp_month": root.cc_exp_month,
            "exp_year": root.cc_exp_year,
            "first_digits": root.cc_first_digits,
            "last_digits": root.cc_last_digits,
        }
        if not any(data.values()):
            return None
        return CreditCard(**data)

    @staticmethod
    def resolve_metadata(root: models.Payment, info):
        permissions = public_payment_permissions(info, root.pk)
        requester = get_user_or_app_from_context(info.context)
        if not requester or not requester.has_perms(permissions):
            raise PermissionDenied(permissions=permissions)
        return resolve_metadata(root.metadata)

    def resolve_checkout(root: models.Payment, info):
        if not root.checkout_id:
            return None
        return CheckoutByTokenLoader(info.context).load(root.checkout_id)


class PaymentCountableConnection(CountableConnection):
    class Meta:
        node = Payment


class PaymentInitialized(BaseObjectType):
    class Meta:
        description = (
            "Server-side data generated by a payment gateway. Optional step when the "
            "payment provider requires an additional action to initialize payment "
            "session."
        )
        doc_category = DOC_CATEGORY_PAYMENTS

    gateway = graphene.String(description="ID of a payment gateway.", required=True)
    name = graphene.String(description="Payment gateway name.", required=True)
    data = JSONString(description="Initialized data by gateway.", required=False)


class TransactionEvent(ModelObjectType[models.TransactionEvent]):
    created_at = graphene.DateTime(required=True)
    status = graphene.Field(
        TransactionEventStatusEnum,
        description="Status of transaction's event.",
        required=False,
        deprecation_reason=(
            f"{PREVIEW_FEATURE_DEPRECATED_IN_313_FIELD} Use `type` instead."
        ),
    )
    reference = graphene.String(
        description="Reference of transaction's event.",
        required=True,
        deprecation_reason=(
            f"{PREVIEW_FEATURE_DEPRECATED_IN_313_FIELD}" "Use `pspReference` instead."
        ),
    )
    psp_reference = graphene.String(
        description="PSP reference of transaction." + ADDED_IN_313, required=True
    )
    name = graphene.String(
        description="Name of the transaction's event.",
        deprecation_reason=(
            f"{PREVIEW_FEATURE_DEPRECATED_IN_313_FIELD} Use `message` instead."
        ),
    )
    message = graphene.String(
        description="Message related to the transaction's event." + ADDED_IN_313,
        required=True,
    )
    external_url = graphene.String(
        description=(
            "The url that will allow to redirect user to "
            "payment provider page with transaction details." + ADDED_IN_313
        ),
        required=True,
    )
    amount = graphene.Field(
        Money,
        required=True,
        description="The amount related to this event." + ADDED_IN_313,
    )
    type = graphene.Field(
        TransactionEventTypeEnum,
        description="The type of action related to this event." + ADDED_IN_313,
    )

    created_by = graphene.Field(
        "saleor.graphql.core.types.user_or_app.UserOrApp",
        description=("User or App that created the transaction event." + ADDED_IN_313),
    )

    class Meta:
        description = "Represents transaction's event."
        interfaces = [relay.Node]
        model = models.TransactionEvent

    @staticmethod
    def resolve_reference(root: models.TransactionEvent, info):
        return root.psp_reference or ""

    @staticmethod
    def resolve_psp_reference(root: models.TransactionEvent, info):
        return root.psp_reference or ""

    @staticmethod
    def resolve_external_url(root: models.TransactionEvent, info):
        return root.external_url or ""

    @staticmethod
    def resolve_name(root: models.TransactionEvent, info):
        return root.message or ""

    @staticmethod
    def resolve_message(root: models.TransactionEvent, info):
        return root.message or ""

    @staticmethod
    def resolve_created_by(root: models.TransactionItem, info):
        """Resolve createdBy.

        Try to fetch the app by db relation first. This cover all apps created manually
        by staff user and the third-party app that was not re-installed.
        If the root.app_id is none, we're trying to fetch the app by `app.identifier`.
        This covers a case when a third-party app was re-installed, but we're still able
        to determine which one is the owner of the transaction.
        """
        if root.app_id:
            return AppByIdLoader(info.context).load(root.app_id)
        if root.app_identifier:

            def get_first_app(apps):
                if apps:
                    return apps[0]
                return None

            return (
                AppsByAppIdentifierLoader(info.context)
                .load(root.app_identifier)
                .then(get_first_app)
            )
        if root.user_id:
            return UserByUserIdLoader(info.context).load(root.user_id)
        return None


class TransactionItem(ModelObjectType[models.TransactionItem]):
    created_at = graphene.DateTime(required=True)
    modified_at = graphene.DateTime(required=True)
    actions = NonNullList(
        TransactionActionEnum,
        description=(
            "List of actions that can be performed in the current state of a payment."
        ),
        required=True,
    )
    authorized_amount = graphene.Field(
        Money, required=True, description="Total amount authorized for this payment."
    )
    authorize_pending_amount = graphene.Field(
        Money,
        required=True,
        description=(
            "Total amount of ongoing authorization requests for the transaction."
            + ADDED_IN_313
        ),
    )
    refunded_amount = graphene.Field(
        Money, required=True, description="Total amount refunded for this payment."
    )
    refund_pending_amount = graphene.Field(
        Money,
        required=True,
        description=(
            "Total amount of ongoing refund requests for the transaction."
            + ADDED_IN_313
        ),
    )
    voided_amount = graphene.Field(
        Money,
        required=True,
        description=("Total amount voided for this payment."),
        deprecation_reason=(
            PREVIEW_FEATURE_DEPRECATED_IN_313_FIELD + "Use `canceledAmount` instead."
        ),
    )

    canceled_amount = graphene.Field(
        Money,
        required=True,
        description="Total amount canceled for this payment." + ADDED_IN_313,
    )
    cancel_pending_amount = graphene.Field(
        Money,
        required=True,
        description=(
            "Total amount of ongoing cancel requests for the transaction."
            + ADDED_IN_313
        ),
    )
    charged_amount = graphene.Field(
        Money, description="Total amount charged for this payment.", required=True
    )
    charge_pending_amount = graphene.Field(
        Money,
        required=True,
        description=(
            "Total amount of ongoing charge requests for the transaction."
            + ADDED_IN_313
        ),
    )
    status = graphene.String(
        description="Status of transaction.",
        deprecation_reason=(
            PREVIEW_FEATURE_DEPRECATED_IN_313_FIELD
            + " The `status` is not needed. The amounts can be used to define "
            "the current status of transactions."
        ),
        required=True,
    )

    type = graphene.String(
        description="Type of transaction.",
        deprecation_reason=(
            PREVIEW_FEATURE_DEPRECATED_IN_313_FIELD
            + " Use `name` or `message` instead."
        ),
        required=True,
    )
    name = graphene.String(
        description="Name of the transaction." + ADDED_IN_313, required=True
    )
    message = graphene.String(
        description="Message related to the transaction." + ADDED_IN_313, required=True
    )

    reference = graphene.String(
        description="Reference of transaction.",
        required=True,
        deprecation_reason=(
            PREVIEW_FEATURE_DEPRECATED_IN_313_FIELD + "Use `pspReference` instead."
        ),
    )
    psp_reference = graphene.String(
        description="PSP reference of transaction." + ADDED_IN_313, required=True
    )
    order = graphene.Field(
        "saleor.graphql.order.types.Order",
        description="The related order." + ADDED_IN_36,
    )
    events = NonNullList(
        TransactionEvent, required=True, description="List of all transaction's events."
    )
    created_by = graphene.Field(
        "saleor.graphql.core.types.user_or_app.UserOrApp",
        description=("User or App that created the transaction." + ADDED_IN_313),
    )
    external_url = graphene.String(
        description=(
            "The url that will allow to redirect user to "
            "payment provider page with transaction details." + ADDED_IN_313
        ),
        required=True,
    )

    class Meta:
        description = (
            "Represents a payment transaction." + ADDED_IN_34 + PREVIEW_FEATURE
        )
        interfaces = [relay.Node, ObjectWithMetadata]
        model = models.TransactionItem

    @staticmethod
    def resolve_actions(root: models.TransactionItem, _info):
        return root.available_actions

    @staticmethod
    def resolve_charged_amount(root: models.TransactionItem, _info):
        return root.amount_charged

    @staticmethod
    def resolve_charge_pending_amount(root: models.TransactionItem, _info):
        return root.amount_charge_pending

    @staticmethod
    def resolve_authorized_amount(root: models.TransactionItem, _info):
        return root.amount_authorized

    @staticmethod
    def resolve_authorize_pending_amount(root: models.TransactionItem, _info):
        return root.amount_authorize_pending

    @staticmethod
    def resolve_voided_amount(root: models.TransactionItem, _info):
        return root.amount_canceled

    @staticmethod
    def resolve_canceled_amount(root: models.TransactionItem, _info):
        return root.amount_canceled

    @staticmethod
    def resolve_cancel_pending_amount(root: models.TransactionItem, _info):
        return root.amount_cancel_pending

    @staticmethod
    def resolve_refunded_amount(root: models.TransactionItem, _info):
        return root.amount_refunded

    @staticmethod
    def resolve_refund_pending_amount(root: models.TransactionItem, _info):
        return root.amount_refund_pending

    @staticmethod
    def resolve_order(root: models.TransactionItem, info):
        if not root.order_id:
            return
        return OrderByIdLoader(info.context).load(root.order_id)

    @staticmethod
    def resolve_events(root: models.TransactionItem, info):
        return TransactionEventByTransactionIdLoader(info.context).load(root.id)

    @staticmethod
    def resolve_created_by(root: models.TransactionItem, info):
        """Resolve createdBy.

        Try to fetch the app by db relation first. This cover all apps created manually
        by staff user and the third-party app that was not re-installed.
        If the root.app_id is none, we're trying to fetch the app by `app.identifier`.
        This covers a case when a third-party app was re-installed, but we're still able
        to determine which one is the owner of the transaction.
        """

        if root.app_id:
            return AppByIdLoader(info.context).load(root.app_id)
        if root.app_identifier:

            def get_first_app(apps):
                if apps:
                    return apps[0]
                return None

            return (
                AppsByAppIdentifierLoader(info.context)
                .load(root.app_identifier)
                .then(get_first_app)
            )
        if root.user_id:
            return UserByUserIdLoader(info.context).load(root.user_id)
        return None

    @staticmethod
    def resolve_reference(root: models.TransactionItem, info):
        return root.psp_reference or ""

    @staticmethod
    def resolve_psp_reference(root: models.TransactionItem, info):
        return root.psp_reference or ""

    @staticmethod
    def resolve_external_url(root: models.TransactionItem, info):
        return root.external_url or ""

    @staticmethod
    def resolve_type(root: models.TransactionItem, info) -> str:
        return root.name or ""

    @staticmethod
    def resolve_name(root: models.TransactionItem, info) -> str:
        return root.name or ""

    @staticmethod
    def resolve_message(root: models.TransactionItem, info) -> str:
        return root.message or ""
