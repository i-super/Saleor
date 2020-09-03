import pytest
from django.contrib.auth.models import AnonymousUser

from ...account import CustomerEvents
from ...account.models import CustomerEvent
from ...core.exceptions import InsufficientStock
from ...core.taxes import zero_money, zero_taxed_money
from ...order import OrderEvents, OrderEventsEmails
from ...order.models import OrderEvent
from ...tests.utils import flush_post_commit_hooks
from .. import calculations
from ..complete_checkout import _create_order, _prepare_order_data
from ..utils import add_variant_to_checkout


def test_create_order_captured_payment_creates_expected_events(
    checkout_with_item, customer_user, shipping_method, payment_txn_captured,
):
    checkout = checkout_with_item
    checkout_user = customer_user

    # Ensure not events are existing prior
    assert not OrderEvent.objects.exists()
    assert not CustomerEvent.objects.exists()

    # Prepare valid checkout
    checkout.user = checkout_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_shipping_address
    checkout.shipping_method = shipping_method
    checkout.payments.add(payment_txn_captured)
    checkout.tracking_code = "tracking_code"
    checkout.redirect_url = "https://www.example.com"
    checkout.save()

    # Place checkout
    order = _create_order(
        checkout=checkout,
        order_data=_prepare_order_data(
            checkout=checkout, lines=list(checkout), discounts=None,
        ),
        user=customer_user,
    )
    flush_post_commit_hooks()

    # Ensure only two events were created, and retrieve them
    order_events = order.events.all()

    (
        order_placed_event,
        payment_captured_event,
        order_fully_paid_event,
        payment_email_sent_event,
        order_placed_email_sent_event,
    ) = order_events  # type: OrderEvent

    # Ensure the correct order event was created
    # is the event the expected type
    assert order_placed_event.type == OrderEvents.PLACED
    # is the user anonymous/ the customer
    assert order_placed_event.user == checkout_user
    # is the associated backref order valid
    assert order_placed_event.order is order
    # ensure a date was set
    assert order_placed_event.date
    # should not have any additional parameters
    assert not order_placed_event.parameters

    # Ensure the correct order event was created
    # is the event the expected type
    assert payment_captured_event.type == OrderEvents.PAYMENT_CAPTURED
    # is the user anonymous/ the customer
    assert payment_captured_event.user == checkout_user
    # is the associated backref order valid
    assert payment_captured_event.order is order
    # ensure a date was set
    assert payment_captured_event.date
    # should not have any additional parameters
    assert "amount" in payment_captured_event.parameters.keys()
    assert "payment_id" in payment_captured_event.parameters.keys()
    assert "payment_gateway" in payment_captured_event.parameters.keys()

    # Ensure the correct order event was created
    # is the event the expected type
    assert order_fully_paid_event.type == OrderEvents.ORDER_FULLY_PAID
    # is the user anonymous/ the customer
    assert order_fully_paid_event.user == checkout_user
    # is the associated backref order valid
    assert order_fully_paid_event.order is order
    # ensure a date was set
    assert order_fully_paid_event.date
    # should not have any additional parameters
    assert not order_fully_paid_event.parameters

    # Ensure the correct email sent event was created
    # should be email sent event
    assert payment_email_sent_event.type == OrderEvents.EMAIL_SENT
    # ensure the user is none or valid
    assert payment_email_sent_event.user == checkout_user
    # ensure the mail event is related to order
    assert payment_email_sent_event.order is order
    # ensure a date was set
    assert payment_email_sent_event.date
    # ensure the correct parameters were set
    assert payment_email_sent_event.parameters == {
        "email": order.get_customer_email(),
        "email_type": OrderEventsEmails.PAYMENT,
    }

    # Ensure the correct email sent event was created
    # should be email sent event
    assert order_placed_email_sent_event.type == OrderEvents.EMAIL_SENT
    # ensure the user is none or valid
    assert order_placed_email_sent_event.user == checkout_user
    # ensure the mail event is related to order
    assert order_placed_email_sent_event.order is order
    # ensure a date was set
    assert order_placed_email_sent_event.date
    # ensure the correct parameters were set
    assert order_placed_email_sent_event.parameters == {
        "email": order.get_customer_email(),
        "email_type": OrderEventsEmails.ORDER_CONFIRMATION,
    }

    # Ensure the correct customer event was created if the user was not anonymous
    placement_event = customer_user.events.get()  # type: CustomerEvent
    assert placement_event.type == CustomerEvents.PLACED_ORDER  # check the event type
    assert placement_event.user == customer_user  # check the backref is valid
    assert placement_event.order == order  # check the associated order is valid
    assert placement_event.date  # ensure a date was set
    assert not placement_event.parameters  # should not have any additional parameters

    # mock_send_staff_order_confirmation.assert_called_once_with(order.pk)


def test_create_order_captured_payment_creates_expected_events_anonymous_user(
    checkout_with_item, customer_user, shipping_method, payment_txn_captured,
):
    checkout = checkout_with_item
    checkout_user = None

    # Ensure not events are existing prior
    assert not OrderEvent.objects.exists()
    assert not CustomerEvent.objects.exists()

    # Prepare valid checkout
    checkout.user = checkout_user
    checkout.email = "test@example.com"
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_shipping_address
    checkout.shipping_method = shipping_method
    checkout.payments.add(payment_txn_captured)
    checkout.tracking_code = "tracking_code"
    checkout.redirect_url = "https://www.example.com"
    checkout.save()

    # Place checkout
    order = _create_order(
        checkout=checkout,
        order_data=_prepare_order_data(
            checkout=checkout, lines=list(checkout), discounts=None,
        ),
        user=AnonymousUser(),
    )
    flush_post_commit_hooks()

    # Ensure only two events were created, and retrieve them
    order_events = order.events.all()

    (
        order_placed_event,
        payment_captured_event,
        order_fully_paid_event,
        payment_email_sent_event,
        order_placed_email_sent_event,
    ) = order_events  # type: OrderEvent

    # Ensure the correct order event was created
    # is the event the expected type
    assert order_placed_event.type == OrderEvents.PLACED
    # is the user anonymous/ the customer
    assert order_placed_event.user == checkout_user
    # is the associated backref order valid
    assert order_placed_event.order is order
    # ensure a date was set
    assert order_placed_event.date
    # should not have any additional parameters
    assert not order_placed_event.parameters

    # Ensure the correct order event was created
    # is the event the expected type
    assert payment_captured_event.type == OrderEvents.PAYMENT_CAPTURED
    # is the user anonymous/ the customer
    assert payment_captured_event.user == checkout_user
    # is the associated backref order valid
    assert payment_captured_event.order is order
    # ensure a date was set
    assert payment_captured_event.date
    # should not have any additional parameters
    assert "amount" in payment_captured_event.parameters.keys()
    assert "payment_id" in payment_captured_event.parameters.keys()
    assert "payment_gateway" in payment_captured_event.parameters.keys()

    # Ensure the correct order event was created
    # is the event the expected type
    assert order_fully_paid_event.type == OrderEvents.ORDER_FULLY_PAID
    # is the user anonymous/ the customer
    assert order_fully_paid_event.user == checkout_user
    # is the associated backref order valid
    assert order_fully_paid_event.order is order
    # ensure a date was set
    assert order_fully_paid_event.date
    # should not have any additional parameters
    assert not order_fully_paid_event.parameters

    # Ensure the correct email sent event was created
    # should be email sent event
    assert payment_email_sent_event.type == OrderEvents.EMAIL_SENT
    # ensure the user is none or valid
    assert payment_email_sent_event.user == checkout_user
    # ensure the mail event is related to order
    assert payment_email_sent_event.order is order
    # ensure a date was set
    assert payment_email_sent_event.date
    # ensure the correct parameters were set
    assert payment_email_sent_event.parameters == {
        "email": order.get_customer_email(),
        "email_type": OrderEventsEmails.PAYMENT,
    }

    # Ensure the correct email sent event was created
    # should be email sent event
    assert order_placed_email_sent_event.type == OrderEvents.EMAIL_SENT
    # ensure the user is none or valid
    assert order_placed_email_sent_event.user == checkout_user
    # ensure the mail event is related to order
    assert order_placed_email_sent_event.order is order
    # ensure a date was set
    assert order_placed_email_sent_event.date
    # ensure the correct parameters were set
    assert order_placed_email_sent_event.parameters == {
        "email": order.get_customer_email(),
        "email_type": OrderEventsEmails.ORDER_CONFIRMATION,
    }

    # Check no event was created if the user was anonymous
    assert not CustomerEvent.objects.exists()  # should not have created any event


def test_create_order_preauth_payment_creates_expected_events(
    checkout_with_item, customer_user, shipping_method, payment_txn_preauth,
):
    checkout = checkout_with_item
    checkout_user = customer_user

    # Ensure not events are existing prior
    assert not OrderEvent.objects.exists()
    assert not CustomerEvent.objects.exists()

    # Prepare valid checkout
    checkout.user = checkout_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_shipping_address
    checkout.shipping_method = shipping_method
    checkout.payments.add(payment_txn_preauth)
    checkout.tracking_code = "tracking_code"
    checkout.redirect_url = "https://www.example.com"
    checkout.save()

    # Place checkout
    order = _create_order(
        checkout=checkout,
        order_data=_prepare_order_data(
            checkout=checkout, lines=list(checkout), discounts=None,
        ),
        user=customer_user,
    )
    flush_post_commit_hooks()

    # Ensure only two events were created, and retrieve them
    order_events = order.events.all()

    (
        order_placed_event,
        payment_authorized_event,
        order_placed_email_sent_event,
    ) = order_events  # type: OrderEvent

    # Ensure the correct order event was created
    # is the event the expected type
    assert order_placed_event.type == OrderEvents.PLACED
    # is the user anonymous/ the customer
    assert order_placed_event.user == checkout_user
    # is the associated backref order valid
    assert order_placed_event.order is order
    # ensure a date was set
    assert order_placed_event.date
    # should not have any additional parameters
    assert not order_placed_event.parameters

    # Ensure the correct order event was created
    # is the event the expected type
    assert payment_authorized_event.type == OrderEvents.PAYMENT_AUTHORIZED
    # is the user anonymous/ the customer
    assert payment_authorized_event.user == checkout_user
    # is the associated backref order valid
    assert payment_authorized_event.order is order
    # ensure a date was set
    assert payment_authorized_event.date
    # should not have any additional parameters
    assert "amount" in payment_authorized_event.parameters.keys()
    assert "payment_id" in payment_authorized_event.parameters.keys()
    assert "payment_gateway" in payment_authorized_event.parameters.keys()

    # Ensure the correct email sent event was created
    # should be email sent event
    assert order_placed_email_sent_event.type == OrderEvents.EMAIL_SENT
    # ensure the user is none or valid
    assert order_placed_email_sent_event.user == checkout_user
    # ensure the mail event is related to order
    assert order_placed_email_sent_event.order is order
    # ensure a date was set
    assert order_placed_email_sent_event.date
    # ensure the correct parameters were set
    assert order_placed_email_sent_event.parameters == {
        "email": order.get_customer_email(),
        "email_type": OrderEventsEmails.ORDER_CONFIRMATION,
    }

    # Ensure the correct customer event was created if the user was not anonymous
    placement_event = customer_user.events.get()  # type: CustomerEvent
    assert placement_event.type == CustomerEvents.PLACED_ORDER  # check the event type
    assert placement_event.user == customer_user  # check the backref is valid
    assert placement_event.order == order  # check the associated order is valid
    assert placement_event.date  # ensure a date was set
    assert not placement_event.parameters  # should not have any additional parameters

    # mock_send_staff_order_confirmation.assert_called_once_with(order.pk)


def test_create_order_preauth_payment_creates_expected_events_anonymous_user(
    checkout_with_item, customer_user, shipping_method, payment_txn_preauth,
):
    checkout = checkout_with_item
    checkout_user = None

    # Ensure not events are existing prior
    assert not OrderEvent.objects.exists()
    assert not CustomerEvent.objects.exists()

    # Prepare valid checkout
    checkout.user = checkout_user
    checkout.email = "test@example.com"
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_shipping_address
    checkout.shipping_method = shipping_method
    checkout.payments.add(payment_txn_preauth)
    checkout.tracking_code = "tracking_code"
    checkout.redirect_url = "https://www.example.com"
    checkout.save()

    # Place checkout
    order = _create_order(
        checkout=checkout,
        order_data=_prepare_order_data(
            checkout=checkout, lines=list(checkout), discounts=None,
        ),
        user=AnonymousUser(),
    )
    flush_post_commit_hooks()

    # Ensure only two events were created, and retrieve them
    order_events = order.events.all()

    (
        order_placed_event,
        payment_captured_event,
        order_placed_email_sent_event,
    ) = order_events  # type: OrderEvent

    # Ensure the correct order event was created
    # is the event the expected type
    assert order_placed_event.type == OrderEvents.PLACED
    # is the user anonymous/ the customer
    assert order_placed_event.user == checkout_user
    # is the associated backref order valid
    assert order_placed_event.order is order
    # ensure a date was set
    assert order_placed_event.date
    # should not have any additional parameters
    assert not order_placed_event.parameters

    # Ensure the correct order event was created
    # is the event the expected type
    assert payment_captured_event.type == OrderEvents.PAYMENT_AUTHORIZED
    # is the user anonymous/ the customer
    assert payment_captured_event.user == checkout_user
    # is the associated backref order valid
    assert payment_captured_event.order is order
    # ensure a date was set
    assert payment_captured_event.date
    # should not have any additional parameters
    assert "amount" in payment_captured_event.parameters.keys()
    assert "payment_id" in payment_captured_event.parameters.keys()
    assert "payment_gateway" in payment_captured_event.parameters.keys()

    # Ensure the correct email sent event was created
    # should be email sent event
    assert order_placed_email_sent_event.type == OrderEvents.EMAIL_SENT
    # ensure the user is none or valid
    assert order_placed_email_sent_event.user == checkout_user
    # ensure the mail event is related to order
    assert order_placed_email_sent_event.order is order
    # ensure a date was set
    assert order_placed_email_sent_event.date
    # ensure the correct parameters were set
    assert order_placed_email_sent_event.parameters == {
        "email": order.get_customer_email(),
        "email_type": OrderEventsEmails.ORDER_CONFIRMATION,
    }

    # Check no event was created if the user was anonymous
    assert not CustomerEvent.objects.exists()  # should not have created any event


def test_create_order_insufficient_stock(
    checkout, customer_user, product_without_shipping
):
    variant = product_without_shipping.variants.get()
    add_variant_to_checkout(checkout, variant, 10, check_quantity=False)
    checkout.user = customer_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_billing_address
    checkout.tracking_code = "tracking_code"
    checkout.save()

    with pytest.raises(InsufficientStock):
        _prepare_order_data(
            checkout=checkout, lines=list(checkout), discounts=None,
        )


def test_create_order_doesnt_duplicate_order(
    checkout_with_item, customer_user, shipping_method
):
    checkout = checkout_with_item
    checkout.user = customer_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_billing_address
    checkout.shipping_method = shipping_method
    checkout.tracking_code = ""
    checkout.redirect_url = "https://www.example.com"
    checkout.save()

    order_data = _prepare_order_data(
        checkout=checkout, lines=list(checkout), discounts=None
    )

    order_1 = _create_order(
        checkout=checkout, order_data=order_data, user=customer_user,
    )
    assert order_1.checkout_token == checkout.token

    order_2 = _create_order(
        checkout=checkout, order_data=order_data, user=customer_user,
    )
    assert order_1.pk == order_2.pk


@pytest.mark.parametrize("is_anonymous_user", (True, False))
def test_create_order_with_gift_card(
    checkout_with_gift_card, customer_user, shipping_method, is_anonymous_user
):
    checkout_user = None if is_anonymous_user else customer_user
    checkout = checkout_with_gift_card
    checkout.user = checkout_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_billing_address
    checkout.shipping_method = shipping_method
    checkout.tracking_code = "tracking_code"
    checkout.redirect_url = "https://www.example.com"
    checkout.save()

    lines = list(checkout)
    subtotal = calculations.checkout_subtotal(checkout=checkout, lines=lines)
    shipping_price = calculations.checkout_shipping_price(
        checkout=checkout, lines=lines
    )
    total_gross_without_gift_cards = (
        subtotal.gross + shipping_price.gross - checkout.discount
    )
    gift_cards_balance = checkout.get_total_gift_cards_balance()

    order = _create_order(
        checkout=checkout,
        order_data=_prepare_order_data(checkout=checkout, lines=lines, discounts=None,),
        user=customer_user if not is_anonymous_user else AnonymousUser(),
    )

    assert order.gift_cards.count() == 1
    assert order.gift_cards.first().current_balance.amount == 0
    assert order.total.gross == (total_gross_without_gift_cards - gift_cards_balance)


def test_create_order_with_gift_card_partial_use(
    checkout_with_item, gift_card_used, customer_user, shipping_method
):
    checkout = checkout_with_item
    checkout.user = customer_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_billing_address
    checkout.shipping_method = shipping_method
    checkout.tracking_code = "tracking_code"
    checkout.redirect_url = "https://www.example.com"
    checkout.save()

    price_without_gift_card = calculations.checkout_total(
        checkout=checkout, lines=list(checkout)
    )
    gift_card_balance_before_order = gift_card_used.current_balance_amount

    checkout.gift_cards.add(gift_card_used)
    checkout.save()

    order = _create_order(
        checkout=checkout,
        order_data=_prepare_order_data(
            checkout=checkout, lines=list(checkout), discounts=None,
        ),
        user=customer_user,
    )

    gift_card_used.refresh_from_db()

    expected_old_balance = (
        price_without_gift_card.gross.amount + gift_card_used.current_balance_amount
    )

    assert order.gift_cards.count() > 0
    assert order.total == zero_taxed_money()
    assert gift_card_balance_before_order == expected_old_balance


def test_create_order_with_many_gift_cards(
    checkout_with_item,
    gift_card_created_by_staff,
    gift_card,
    customer_user,
    shipping_method,
):
    checkout = checkout_with_item
    checkout.user = customer_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_billing_address
    checkout.shipping_method = shipping_method
    checkout.tracking_code = "tracking_code"
    checkout.redirect_url = "https://www.example.com"
    checkout.save()

    price_without_gift_card = calculations.checkout_total(
        checkout=checkout, lines=list(checkout)
    )
    gift_cards_balance_before_order = (
        gift_card_created_by_staff.current_balance.amount
        + gift_card.current_balance.amount
    )

    checkout.gift_cards.add(gift_card_created_by_staff)
    checkout.gift_cards.add(gift_card)
    checkout.save()

    order = _create_order(
        checkout=checkout,
        order_data=_prepare_order_data(
            checkout=checkout, lines=list(checkout), discounts=None,
        ),
        user=customer_user,
    )

    gift_card_created_by_staff.refresh_from_db()
    gift_card.refresh_from_db()
    zero_price = zero_money()
    assert order.gift_cards.count() > 0
    assert gift_card_created_by_staff.current_balance == zero_price
    assert gift_card.current_balance == zero_price
    assert price_without_gift_card.gross.amount == (
        gift_cards_balance_before_order + order.total.gross.amount
    )


def test_note_in_created_order(checkout_with_item, address, customer_user):
    checkout_with_item.shipping_address = address
    checkout_with_item.note = "test_note"
    checkout_with_item.tracking_code = "tracking_code"
    checkout_with_item.redirect_url = "https://www.example.com"
    checkout_with_item.save()
    order = _create_order(
        checkout=checkout_with_item,
        order_data=_prepare_order_data(
            checkout=checkout_with_item, lines=list(checkout_with_item), discounts=None,
        ),
        user=customer_user,
    )
    assert order.customer_note == checkout_with_item.note


def test_create_order_with_variant_tracking_false(
    checkout, customer_user, variant_without_inventory_tracking
):
    variant = variant_without_inventory_tracking
    checkout.user = customer_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_billing_address
    checkout.tracking_code = ""
    checkout.redirect_url = "https://www.example.com"
    checkout.save()
    add_variant_to_checkout(checkout, variant, 10, check_quantity=False)

    order_data = _prepare_order_data(
        checkout=checkout, lines=list(checkout), discounts=None
    )

    order_1 = _create_order(
        checkout=checkout, order_data=order_data, user=customer_user,
    )
    assert order_1.checkout_token == checkout.token
