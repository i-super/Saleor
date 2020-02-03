import copy
import json

import pytest

from saleor.order import OrderStatus
from saleor.webhook.event_types import WebhookEventType
from saleor.webhook.payloads import (
    generate_checkout_payload,
    generate_order_payload,
    generate_product_payload,
    generate_sample_payload,
)


def _remove_anonymized_order_data(order_data: dict) -> dict:
    order_data = copy.deepcopy(order_data)
    del order_data[0]["id"]
    del order_data[0]["user_email"]
    del order_data[0]["billing_address"]
    del order_data[0]["shipping_address"]
    del order_data[0]["meta"]
    del order_data[0]["private_meta"]
    return order_data


@pytest.mark.parametrize(
    "event_name, order_status",
    [
        (WebhookEventType.ORDER_CREATED, OrderStatus.UNFULFILLED),
        (WebhookEventType.ORDER_UPDATED, OrderStatus.CANCELED),
        (WebhookEventType.ORDER_CANCELLED, OrderStatus.CANCELED),
        (WebhookEventType.ORDER_FULFILLED, OrderStatus.FULFILLED),
        (WebhookEventType.ORDER_FULLY_PAID, OrderStatus.FULFILLED),
    ],
)
def test_generate_sample_payload_order(
    event_name, order_status, fulfilled_order, payment_txn_captured
):
    order = fulfilled_order
    order.status = order_status
    order.save()
    payload = generate_sample_payload(event_name)
    order_payload = json.loads(generate_order_payload(fulfilled_order))
    # Check anonymized data differ
    assert order.id != payload[0]["id"]
    assert order.user_email != payload[0]["user_email"]
    assert (
        order.billing_address.street_address_1
        != payload[0]["billing_address"]["street_address_1"]
    )
    assert (
        order.shipping_address.street_address_1
        != payload[0]["shipping_address"]["street_address_1"]
    )
    assert order.meta != payload[0]["meta"]
    assert order.private_meta != payload[0]["private_meta"]
    # Remove anonymized data
    payload = _remove_anonymized_order_data(payload)
    order_payload = _remove_anonymized_order_data(order_payload)
    # Compare the payloads
    assert payload == order_payload


@pytest.mark.parametrize(
    "event_name",
    [
        WebhookEventType.ORDER_CREATED,
        WebhookEventType.ORDER_UPDATED,
        WebhookEventType.ORDER_CANCELLED,
        WebhookEventType.ORDER_FULFILLED,
        WebhookEventType.ORDER_FULLY_PAID,
        WebhookEventType.PRODUCT_CREATED,
        "Non_existing_event",
        None,
        "",
    ],
)
def test_generate_sample_payload_empty_response_(event_name):
    assert generate_sample_payload(event_name) is None


def test_generate_sample_customer_payload(customer_user):
    payload = generate_sample_payload(WebhookEventType.CUSTOMER_CREATED)
    assert payload
    # Assert that the payload was generated from the fake user
    assert payload[0]["email"] != customer_user.email


def test_generate_sample_product_payload(variant):
    payload = generate_sample_payload(WebhookEventType.PRODUCT_CREATED)
    assert payload == json.loads(generate_product_payload(variant.product))


def _remove_anonymized_checkout_data(checkout_data: dict) -> dict:
    checkout_data = copy.deepcopy(checkout_data)
    del checkout_data[0]["token"]
    del checkout_data[0]["user"]
    del checkout_data[0]["email"]
    del checkout_data[0]["billing_address"]
    del checkout_data[0]["shipping_address"]
    del checkout_data[0]["meta"]
    del checkout_data[0]["private_meta"]
    return checkout_data


def test_generate_sample_checkout_payload(user_checkout_with_items):
    checkout = user_checkout_with_items
    payload = generate_sample_payload(WebhookEventType.CHECKOUT_QUANTITY_CHANGED)
    checkout_payload = json.loads(generate_checkout_payload(checkout))
    # Check anonymized data differ
    assert checkout.token != payload[0]["token"]
    assert checkout.user.email != payload[0]["user"]["email"]
    assert checkout.email != payload[0]["email"]
    assert (
        checkout.billing_address.street_address_1
        != payload[0]["billing_address"]["street_address_1"]
    )
    assert (
        checkout.shipping_address.street_address_1
        != payload[0]["shipping_address"]["street_address_1"]
    )
    assert "note" not in payload[0]
    assert checkout.meta != payload[0]["meta"]
    assert checkout.private_meta != payload[0]["private_meta"]
    # Remove anonymized data
    payload = _remove_anonymized_checkout_data(payload)
    checkout_payload = _remove_anonymized_checkout_data(checkout_payload)
    # Compare the payloads
    assert payload == checkout_payload
