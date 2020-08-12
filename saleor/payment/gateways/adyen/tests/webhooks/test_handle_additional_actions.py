import json
import uuid
from unittest import mock
from urllib.parse import quote_plus

import graphene

from ..... import PaymentError, TransactionKind
from ...webhooks import handle_additional_actions


@mock.patch("saleor.payment.gateways.adyen.webhooks.api_call")
def test_handle_additional_actions_post(api_call_mock, payment_adyen_for_checkout):
    # given
    payment_adyen_for_checkout.extra_data = json.dumps(
        [{"payment_data": "test_data", "parameters": ["payload"]}]
    )
    payment_adyen_for_checkout.save(update_fields=["extra_data"])

    transaction_count = payment_adyen_for_checkout.transactions.all().count()

    checkout = payment_adyen_for_checkout.checkout
    payment_id = graphene.Node.to_global_id("Payment", payment_adyen_for_checkout.pk)
    checkout_id = graphene.Node.to_global_id("Checkout", checkout.pk)

    request_mock = mock.Mock()
    request_mock.GET = {"payment": payment_id, "checkout": checkout.pk}
    request_mock.POST = {"payload": "test"}

    payment_details_mock = mock.Mock()
    message = {
        "resultCode": "Test",
    }
    api_call_mock.return_value.message = message

    # when
    response = handle_additional_actions(request_mock, payment_details_mock)

    # then
    payment_adyen_for_checkout.refresh_from_db()
    assert response.status_code == 302
    assert f"checkout={quote_plus(checkout_id)}" in response.url
    assert f"resultCode={message['resultCode']}" in response.url
    assert f"payment={quote_plus(payment_id)}" in response.url
    assert (
        payment_adyen_for_checkout.transactions.all().count() == transaction_count + 1
    )
    transaction = payment_adyen_for_checkout.transactions.last()
    assert transaction.kind == TransactionKind.ACTION_TO_CONFIRM


@mock.patch("saleor.payment.gateways.adyen.webhooks.api_call")
def test_handle_additional_actions_get(api_call_mock, payment_adyen_for_checkout):
    # given
    payment_adyen_for_checkout.extra_data = json.dumps(
        {"payment_data": "test_data", "parameters": ["payload"]}
    )
    payment_adyen_for_checkout.save(update_fields=["extra_data"])

    transaction_count = payment_adyen_for_checkout.transactions.all().count()

    checkout = payment_adyen_for_checkout.checkout
    payment_id = graphene.Node.to_global_id("Payment", payment_adyen_for_checkout.pk)
    checkout_id = graphene.Node.to_global_id("Checkout", checkout.pk)

    request_mock = mock.Mock()
    request_mock.GET = {
        "payment": payment_id,
        "checkout": checkout.pk,
        "payload": "test",
    }

    payment_details_mock = mock.Mock()
    message = {
        "resultCode": "Test",
    }
    api_call_mock.return_value.message = message

    # when
    response = handle_additional_actions(request_mock, payment_details_mock)

    # then
    payment_adyen_for_checkout.refresh_from_db()
    assert response.status_code == 302
    assert f"checkout={quote_plus(checkout_id)}" in response.url
    assert f"resultCode={message['resultCode']}" in response.url
    assert f"payment={quote_plus(payment_id)}" in response.url
    assert (
        payment_adyen_for_checkout.transactions.all().count() == transaction_count + 1
    )
    transaction = payment_adyen_for_checkout.transactions.last()
    assert transaction.kind == TransactionKind.ACTION_TO_CONFIRM


def test_handle_additional_actions_more_action_required(payment_adyen_for_checkout):
    # given
    payment_adyen_for_checkout.extra_data = json.dumps(
        {"payment_data": "test_data", "parameters": ["payload"]}
    )
    payment_adyen_for_checkout.save(update_fields=["extra_data"])

    checkout = payment_adyen_for_checkout.checkout
    payment_id = graphene.Node.to_global_id("Payment", payment_adyen_for_checkout.pk)
    checkout_id = graphene.Node.to_global_id("Checkout", checkout.pk)

    request_mock = mock.Mock()
    request_mock.GET = {"payment": payment_id, "checkout": checkout.pk}
    request_mock.POST = {"payload": "test"}

    payment_details_mock = mock.Mock()
    message = {
        "resultCode": "Pending",
        "action": {
            "method": "GET",
            "paymentData": "123",
            "paymentMethodType": "ideal",
            "type": "redirect",
            "url": "https://test.adyen.com/hpp/redirectIdeal.shtml?brandCode=ideal",
        },
    }
    payment_details_mock.return_value.message = message

    # when
    response = handle_additional_actions(request_mock, payment_details_mock)

    # then
    assert response.status_code == 302
    assert f"resultCode={message['resultCode']}" in response.url
    assert f"method={message['action']['method']}" in response.url
    assert f"paymentData={message['action']['paymentData']}" in response.url
    assert f"paymentMethodType={message['action']['paymentMethodType']}" in response.url
    assert f"type={message['action']['type']}" in response.url
    assert f"checkout={quote_plus(checkout_id)}" in response.url
    assert f"payment={quote_plus(payment_id)}" in response.url

    transaction = payment_adyen_for_checkout.transactions.last()
    assert transaction.kind == TransactionKind.ACTION_TO_CONFIRM
    assert transaction.action_required is True


def test_handle_additional_actions_payment_does_not_exist(payment_adyen_for_checkout):
    # given
    payment_adyen_for_checkout.extra_data = json.dumps(
        {"payment_data": "test_data", "parameters": ["payload"]}
    )
    payment_adyen_for_checkout.save(update_fields=["extra_data"])

    payment_id = graphene.Node.to_global_id("Payment", payment_adyen_for_checkout.pk)
    request_mock = mock.Mock()
    request_mock.GET = {
        "payment": payment_id,
        "checkout": payment_adyen_for_checkout.checkout.pk,
    }
    request_mock.POST = {"payload": "test"}

    payment_details_mock = mock.Mock()
    payment_details_mock.return_value.message = {
        "resultCode": "Test",
    }

    payment_adyen_for_checkout.delete()

    # when
    response = handle_additional_actions(request_mock, payment_details_mock)

    # then
    assert response.status_code == 404
    assert response.content.decode() == (
        "Cannot perform payment. "
        "There is no active adyen payment with specified checkout."
    )


def test_handle_additional_actions_payment_lack_of_return_url(
    payment_adyen_for_checkout,
):
    # given
    payment_adyen_for_checkout.extra_data = json.dumps(
        {"payment_data": "test_data", "parameters": ["payload"]}
    )
    payment_adyen_for_checkout.return_url = None
    payment_adyen_for_checkout.save(update_fields=["extra_data", "return_url"])

    payment_id = graphene.Node.to_global_id("Payment", payment_adyen_for_checkout.pk)
    request_mock = mock.Mock()
    request_mock.GET = {
        "payment": payment_id,
        "checkout": payment_adyen_for_checkout.checkout.pk,
    }
    request_mock.POST = {"payload": "test"}

    payment_details_mock = mock.Mock()
    payment_details_mock.return_value.message = {
        "resultCode": "Test",
    }

    # when
    response = handle_additional_actions(request_mock, payment_details_mock)

    # then
    assert response.status_code == 404
    assert (
        response.content.decode()
        == "Cannot perform payment. Lack of data about returnUrl."
    )


def test_handle_additional_actions_no_payment_id_in_get(payment_adyen_for_checkout):
    # given
    payment_adyen_for_checkout.extra_data = json.dumps(
        {"payment_data": "test_data", "parameters": ["payload"]}
    )
    payment_adyen_for_checkout.save(update_fields=["extra_data"])

    request_mock = mock.Mock()
    request_mock.GET = {}
    request_mock.POST = {"payload": "test"}

    payment_details_mock = mock.Mock()
    message = {
        "resultCode": "Test",
    }
    payment_details_mock.return_value.message = message

    # when
    response = handle_additional_actions(request_mock, payment_details_mock)

    # then
    assert response.status_code == 404


def test_handle_additional_actions_checkout_not_related_to_payment(
    payment_adyen_for_checkout,
):
    # given
    payment_adyen_for_checkout.extra_data = json.dumps(
        {"payment_data": "test_data", "parameters": ["payload"]}
    )
    payment_adyen_for_checkout.save(update_fields=["extra_data"])

    payment_id = graphene.Node.to_global_id("Payment", payment_adyen_for_checkout.pk)

    request_mock = mock.Mock()
    request_mock.GET = {"payment": payment_id, "checkout": uuid.uuid4()}
    request_mock.POST = {"payload": "test"}

    payment_details_mock = mock.Mock()
    message = {
        "resultCode": "Test",
    }
    payment_details_mock.return_value.message = message

    # when
    response = handle_additional_actions(request_mock, payment_details_mock)

    # then
    assert response.status_code == 404
    assert response.content.decode() == (
        "Cannot perform payment. "
        "There is no active adyen payment with specified checkout."
    )


def test_handle_additional_actions_payment_does_not_have_checkout(
    payment_adyen_for_checkout,
):
    # given
    payment_adyen_for_checkout.extra_data = json.dumps(
        {"payment_data": "test_data", "parameters": ["payload"]}
    )
    payment_adyen_for_checkout.checkout = None
    payment_adyen_for_checkout.save()

    payment_id = graphene.Node.to_global_id("Payment", payment_adyen_for_checkout.pk)

    request_mock = mock.Mock()
    request_mock.GET = {"payment": payment_id, "checkout": uuid.uuid4()}
    request_mock.POST = {"payload": "test"}

    payment_details_mock = mock.Mock()
    message = {
        "resultCode": "Test",
    }
    payment_details_mock.return_value.message = message

    # when
    response = handle_additional_actions(request_mock, payment_details_mock)

    # then
    assert response.status_code == 404
    assert response.content.decode() == (
        "Cannot perform payment. "
        "There is no active adyen payment with specified checkout."
    )


@mock.patch("saleor.payment.gateways.adyen.webhooks.api_call")
def test_handle_additional_actions_api_call_error(
    api_call_mock, payment_adyen_for_checkout,
):
    # given
    payment_adyen_for_checkout.extra_data = json.dumps(
        {"payment_data": "test_data", "parameters": ["payload"]}
    )
    payment_adyen_for_checkout.save()

    payment_id = graphene.Node.to_global_id("Payment", payment_adyen_for_checkout.pk)

    error_message = "Test error"
    api_call_mock.side_effect = PaymentError(error_message)

    request_mock = mock.Mock()
    request_mock.GET = {
        "payment": payment_id,
        "checkout": payment_adyen_for_checkout.checkout.pk,
    }
    request_mock.POST = {"payload": "test"}

    payment_details_mock = mock.Mock()
    message = {
        "resultCode": "Test",
    }
    payment_details_mock.return_value.message = message

    # when
    response = handle_additional_actions(request_mock, payment_details_mock)

    # then
    assert response.status_code == 400
    assert response.content.decode() == error_message


def test_handle_additional_actions_payment_not_active(payment_adyen_for_checkout):
    # given
    payment_adyen_for_checkout.extra_data = json.dumps(
        {"payment_data": "test_data", "parameters": ["payload"]}
    )
    payment_adyen_for_checkout.is_active = False
    payment_adyen_for_checkout.save(update_fields=["extra_data", "is_active"])

    checkout = payment_adyen_for_checkout.checkout
    payment_id = graphene.Node.to_global_id("Payment", payment_adyen_for_checkout.pk)

    request_mock = mock.Mock()
    request_mock.GET = {"payment": payment_id, "checkout": checkout.pk}
    request_mock.POST = {"payload": "test"}

    payment_details_mock = mock.Mock()
    message = {
        "resultCode": "Test",
    }
    payment_details_mock.return_value.message = message

    # when
    response = handle_additional_actions(request_mock, payment_details_mock)

    # then
    assert response.status_code == 404
    assert response.content.decode() == (
        "Cannot perform payment. "
        "There is no active adyen payment with specified checkout."
    )


def test_handle_additional_actions_payment_with_no_adyen_gateway(
    payment_adyen_for_checkout,
):
    # given
    payment_adyen_for_checkout.extra_data = json.dumps(
        {"payment_data": "test_data", "parameters": ["payload"]}
    )
    payment_adyen_for_checkout.gateway = "test"
    payment_adyen_for_checkout.save(update_fields=["extra_data", "gateway"])

    checkout = payment_adyen_for_checkout.checkout
    payment_id = graphene.Node.to_global_id("Payment", payment_adyen_for_checkout.pk)

    request_mock = mock.Mock()
    request_mock.GET = {"payment": payment_id, "checkout": checkout.pk}
    request_mock.POST = {"payload": "test"}

    payment_details_mock = mock.Mock()
    message = {
        "resultCode": "Test",
    }
    payment_details_mock.return_value.message = message

    # when
    response = handle_additional_actions(request_mock, payment_details_mock)

    # then
    assert response.status_code == 404
    assert response.content.decode() == (
        "Cannot perform payment. "
        "There is no active adyen payment with specified checkout."
    )


@mock.patch("saleor.payment.gateways.adyen.webhooks.api_call")
def test_handle_additional_actions_lack_of_parameter_in_request(
    api_call_mock, payment_adyen_for_checkout
):
    # given
    payment_adyen_for_checkout.extra_data = json.dumps(
        {"payment_data": "test_data", "parameters": ["payload", "second_param"]}
    )
    payment_adyen_for_checkout.save(update_fields=["extra_data"])

    checkout = payment_adyen_for_checkout.checkout
    payment_id = graphene.Node.to_global_id("Payment", payment_adyen_for_checkout.pk)

    request_mock = mock.Mock()
    request_mock.GET = {"payment": payment_id, "checkout": checkout.pk}
    request_mock.POST = {"payload": "test"}

    payment_details_mock = mock.Mock()
    message = {
        "resultCode": "Test",
    }
    api_call_mock.return_value.message = message

    # when
    response = handle_additional_actions(request_mock, payment_details_mock)

    # then
    payment_adyen_for_checkout.refresh_from_db()
    assert response.status_code == 400
    assert (
        response.content.decode()
        == "Cannot perform payment. Lack of required parameters in request."
    )
