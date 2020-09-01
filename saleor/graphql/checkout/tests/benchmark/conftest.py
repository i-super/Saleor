import pytest

from .....checkout import calculations
from .....checkout.utils import add_variant_to_checkout
from .....payment import ChargeStatus, TransactionKind
from .....payment.models import Payment


@pytest.fixture
def customer_checkout(customer_user, checkout_with_voucher_percentage_and_shipping):
    checkout_with_voucher_percentage_and_shipping.user = customer_user
    checkout_with_voucher_percentage_and_shipping.save()
    return checkout_with_voucher_percentage_and_shipping


@pytest.fixture()
def checkout_with_variants(
    checkout,
    stock,
    product_with_default_variant,
    product_with_single_variant,
    product_with_two_variants,
):

    add_variant_to_checkout(checkout, product_with_default_variant.variants.get(), 1)
    add_variant_to_checkout(checkout, product_with_single_variant.variants.get(), 10)
    add_variant_to_checkout(checkout, product_with_two_variants.variants.first(), 3)
    add_variant_to_checkout(checkout, product_with_two_variants.variants.last(), 5)

    checkout.save()
    return checkout


@pytest.fixture()
def checkout_with_shipping_address(checkout_with_variants, address):
    checkout = checkout_with_variants

    checkout.shipping_address = address.get_copy()
    checkout.save()

    return checkout


@pytest.fixture()
def checkout_with_shipping_method(checkout_with_shipping_address, shipping_method):
    checkout = checkout_with_shipping_address

    checkout.shipping_method = shipping_method
    checkout.save()

    return checkout


@pytest.fixture()
def checkout_with_billing_address(checkout_with_shipping_method, address):
    checkout = checkout_with_shipping_method

    checkout.billing_address = address
    checkout.save()

    return checkout


@pytest.fixture()
def checkout_with_charged_payment(checkout_with_billing_address):
    checkout = checkout_with_billing_address

    taxed_total = calculations.checkout_total(checkout=checkout, lines=list(checkout))
    payment = Payment.objects.create(
        gateway="mirumee.payments.dummy",
        is_active=True,
        total=taxed_total.gross.amount,
        currency="USD",
    )

    payment.charge_status = ChargeStatus.FULLY_CHARGED
    payment.captured_amount = payment.total
    payment.checkout = checkout_with_billing_address
    payment.save()

    payment.transactions.create(
        amount=payment.total,
        kind=TransactionKind.CAPTURE,
        gateway_response={},
        is_success=True,
    )

    return checkout
