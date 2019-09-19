import json
import logging
from decimal import Decimal
from typing import Dict, List

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils.translation import pgettext_lazy

from ..account.models import Address, User
from ..checkout.models import Checkout
from ..core import analytics
from ..order import events, utils as order_utils
from ..order.emails import send_payment_confirmation
from ..order.models import Order
from . import (
    ChargeStatus,
    CustomPaymentChoices,
    GatewayError,
    PaymentError,
    TransactionKind,
    get_payment_gateway,
)
from .interface import AddressData, GatewayResponse, PaymentData, TokenConfig
from .models import Payment, Transaction

logger = logging.getLogger(__name__)

GENERIC_TRANSACTION_ERROR = "Transaction was unsuccessful"
ALLOWED_GATEWAY_KINDS = {choices[0] for choices in TransactionKind.CHOICES}
GATEWAYS_META_NAMESPACE = "payment-gateways"


def list_enabled_gateways() -> List[str]:
    return list(settings.CHECKOUT_PAYMENT_GATEWAYS.keys())


def create_payment_information(
    payment: Payment,
    payment_token: str = None,
    amount: Decimal = None,
    billing_address: AddressData = None,
    shipping_address: AddressData = None,
    customer_id: str = None,
    store_source: bool = False,
) -> PaymentData:
    """Extract order information along with payment details.

    Returns information required to process payment and additional
    billing/shipping addresses for optional fraud-prevention mechanisms.
    """
    billing, shipping = None, None

    if billing_address is None and payment.order and payment.order.billing_address:
        billing = AddressData(**payment.order.billing_address.as_data())

    if shipping_address is None and payment.order and payment.order.shipping_address:
        shipping = AddressData(**payment.order.shipping_address.as_data())

    order_id = payment.order.pk if payment.order else None

    return PaymentData(
        token=payment_token,
        amount=amount or payment.total,
        currency=payment.currency,
        billing=billing or billing_address,
        shipping=shipping or shipping_address,
        order_id=order_id,
        customer_ip_address=payment.customer_ip_address,
        customer_id=customer_id,
        customer_email=payment.billing_email,
        reuse_source=store_source,
    )


def handle_fully_paid_order(order):
    events.order_fully_paid_event(order=order)

    if order.get_customer_email():
        events.email_sent_event(
            order=order, user=None, email_type=events.OrderEventsEmails.PAYMENT
        )
        send_payment_confirmation.delay(order.pk)

        if order_utils.order_needs_automatic_fullfilment(order):
            order_utils.automatically_fulfill_digital_lines(order)
    try:
        analytics.report_order(order.tracking_client_id, order)
    except Exception:
        # Analytics failing should not abort the checkout flow
        logger.exception("Recording order in analytics failed")


def create_payment(
    gateway: str,
    total: Decimal,
    currency: str,
    email: str,
    billing_address: Address,
    customer_ip_address: str = "",
    payment_token: str = "",
    extra_data: Dict = None,
    checkout: Checkout = None,
    order: Order = None,
) -> Payment:
    """Create a payment instance.

    This method is responsible for creating payment instances that works for
    both Django views and GraphQL mutations.
    """
    defaults = {
        "billing_email": email,
        "billing_first_name": billing_address.first_name,
        "billing_last_name": billing_address.last_name,
        "billing_company_name": billing_address.company_name,
        "billing_address_1": billing_address.street_address_1,
        "billing_address_2": billing_address.street_address_2,
        "billing_city": billing_address.city,
        "billing_postal_code": billing_address.postal_code,
        "billing_country_code": billing_address.country.code,
        "billing_country_area": billing_address.country_area,
        "currency": currency,
        "gateway": gateway,
        "total": total,
    }

    if extra_data is None:
        extra_data = {}

    data = {
        "is_active": True,
        "customer_ip_address": customer_ip_address,
        "extra_data": extra_data,
        "token": payment_token,
    }

    if order is not None:
        data["order"] = order
    if checkout is not None:
        data["checkout"] = checkout

    payment, _ = Payment.objects.get_or_create(defaults=defaults, **data)
    return payment


@transaction.atomic
def mark_order_as_paid(order: Order, request_user: User):
    """Mark order as paid.

    Allows to create a payment for an order without actually performing any
    payment by the gateway.
    """
    payment = create_payment(
        gateway=CustomPaymentChoices.MANUAL,
        payment_token="",
        currency=order.total.gross.currency,
        email=order.user_email,
        billing_address=order.billing_address,
        total=order.total.gross.amount,
        order=order,
    )
    payment.charge_status = ChargeStatus.FULLY_CHARGED
    payment.captured_amount = order.total.gross.amount
    payment.save(update_fields=["captured_amount", "charge_status"])
    events.order_manually_marked_as_paid_event(order=order, user=request_user)


def create_transaction(
    payment: Payment,
    kind: str,
    payment_information: PaymentData,
    gateway_response: GatewayResponse = None,
    error_msg=None,
) -> Transaction:
    """Create a transaction based on transaction kind and gateway response."""
    # Default values for token, amount, currency are only used in cases where
    # response from gateway was invalid or an exception occured
    if not gateway_response:
        gateway_response = GatewayResponse(
            kind=kind,
            action_required=False,
            transaction_id=payment_information.token,
            is_success=False,
            amount=payment_information.amount,
            currency=payment_information.currency,
            error=error_msg,
            raw_response={},
        )

    txn = Transaction.objects.create(
        payment=payment,
        kind=gateway_response.kind,
        token=gateway_response.transaction_id,
        is_success=gateway_response.is_success,
        amount=gateway_response.amount,
        currency=gateway_response.currency,
        error=gateway_response.error,
        customer_id=gateway_response.customer_id,
        gateway_response=gateway_response.raw_response or {},
    )
    return txn


def gateway_get_client_token(gateway_name: str, token_config: TokenConfig = None):
    """Get a client token.

    That will be used as a customer's identificator for client-side tokenization
    of the chosen payment method.
    """
    if not token_config:
        token_config = TokenConfig()
    gateway, gateway_config = get_payment_gateway(gateway_name)
    return gateway.get_client_token(config=gateway_config, token_config=token_config)


def clean_capture(payment: Payment, amount: Decimal):
    """Check if payment can be captured."""
    if amount <= 0:
        raise PaymentError("Amount should be a positive number.")
    if not payment.can_capture():
        raise PaymentError("This payment cannot be captured.")
    if amount > payment.total or amount > (payment.total - payment.captured_amount):
        raise PaymentError("Unable to charge more than un-captured amount.")


def clean_authorize(payment: Payment):
    """Check if payment can be authorized."""
    if not payment.can_authorize():
        raise PaymentError("Charged transactions cannot be authorized again.")


def clean_mark_order_as_paid(order: Order):
    """Check if an order can be marked as paid."""
    if order.payments.exists():
        raise PaymentError(
            pgettext_lazy(
                "Mark order as paid validation error",
                "Orders with payments can not be manually marked as paid.",
            )
        )


def validate_gateway_response(response: GatewayResponse):
    """Validate response to be a correct format for Saleor to process."""
    if not isinstance(response, GatewayResponse):
        raise GatewayError("Gateway needs to return a GatewayResponse obj")

    if response.kind not in ALLOWED_GATEWAY_KINDS:
        raise GatewayError(
            "Gateway response kind must be one of {}".format(
                sorted(ALLOWED_GATEWAY_KINDS)
            )
        )

    if response.currency != settings.DEFAULT_CURRENCY:
        logger.warning("Transaction currency is different than Saleor's.")

    try:
        json.dumps(response.raw_response, cls=DjangoJSONEncoder)
    except (TypeError, ValueError):
        raise GatewayError("Gateway response needs to be json serializable")


@transaction.atomic
def gateway_postprocess(transaction, payment):
    if not transaction.is_success:
        return

    transaction_kind = transaction.kind

    if transaction_kind in {TransactionKind.CAPTURE, TransactionKind.CONFIRM}:
        payment.captured_amount += Decimal(transaction.amount)

        # Set payment charge status to fully charged
        # only if there is no more amount needs to charge
        payment.charge_status = ChargeStatus.PARTIALLY_CHARGED
        if payment.get_charge_amount() <= 0:
            payment.charge_status = ChargeStatus.FULLY_CHARGED

        payment.save(update_fields=["charge_status", "captured_amount"])
        order = payment.order
        if order and order.is_fully_paid():
            handle_fully_paid_order(order)

    elif transaction_kind == TransactionKind.VOID:
        payment.is_active = False
        payment.save(update_fields=["is_active"])

    elif transaction_kind == TransactionKind.REFUND:
        changed_fields = ["captured_amount"]
        payment.captured_amount -= transaction.amount
        payment.charge_status = ChargeStatus.PARTIALLY_REFUNDED
        if payment.captured_amount <= 0:
            payment.charge_status = ChargeStatus.FULLY_REFUNDED
            payment.is_active = False
        changed_fields += ["charge_status", "is_active"]
        payment.save(update_fields=changed_fields)


def fetch_customer_id(user, gateway):
    """Retrieve users customer_id stored for desired gateway."""
    key = prepare_namespace_name(gateway)
    gateway_config = user.get_private_meta(
        namespace=GATEWAYS_META_NAMESPACE, client=key
    )
    return gateway_config.get("customer_id", None)


def store_customer_id(user, gateway, customer_id):
    """Store customer_id in users private meta for desired gateway."""
    user.store_private_meta(
        namespace=GATEWAYS_META_NAMESPACE,
        client=prepare_namespace_name(gateway),
        item={"customer_id": customer_id},
    )
    user.save(update_fields=["private_meta"])


def prepare_namespace_name(s):
    return s.strip().upper()


def retrieve_customer_sources(gateway_name, customer_id):
    """Fetch all customer payment sources stored in gateway."""
    gateway, config = get_payment_gateway(gateway_name)
    return gateway.list_client_sources(config, customer_id)


def update_card_details(payment, gateway_response):
    payment.cc_brand = gateway_response.card_info.brand or ""
    payment.cc_last_digits = gateway_response.card_info.last_4
    payment.cc_exp_year = gateway_response.card_info.exp_year
    payment.cc_exp_month = gateway_response.card_info.exp_month
    payment.save(
        update_fields=["cc_brand", "cc_last_digits", "cc_exp_year", "cc_exp_month"]
    )


def get_payment_token(payment: Payment):
    auth_transaction = payment.transactions.filter(
        kind=TransactionKind.AUTH, is_success=True
    ).first()
    if auth_transaction is None:
        raise PaymentError("Cannot process unauthorized transaction")
    return auth_transaction.token
