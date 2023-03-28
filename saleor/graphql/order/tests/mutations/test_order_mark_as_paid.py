import graphene
import pytest
from prices import Money, TaxedMoney

from .....channel import MarkAsPaidStrategy
from .....order import OrderStatus
from .....order import events as order_events
from .....order.error_codes import OrderErrorCode
from .....payment import TransactionEventType
from ....tests.utils import get_graphql_content

MUTATION_MARK_ORDER_AS_PAID = """
    mutation markPaid($id: ID!, $transaction: String) {
        orderMarkAsPaid(id: $id, transactionReference: $transaction) {
            errors {
                field
                message
            }
            errors {
                field
                message
                code
            }
            order {
                isPaid
                events{
                    transactionReference
                }
            }
        }
    }
"""


def test_paid_order_mark_as_paid_with_payment(
    staff_api_client, permission_manage_orders, payment_txn_preauth
):
    order = payment_txn_preauth.order
    query = MUTATION_MARK_ORDER_AS_PAID
    order_id = graphene.Node.to_global_id("Order", order.id)
    variables = {"id": order_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    errors = content["data"]["orderMarkAsPaid"]["errors"]
    msg = "Orders with payments can not be manually marked as paid."
    assert errors[0]["message"] == msg
    assert errors[0]["field"] == "payment"

    order_errors = content["data"]["orderMarkAsPaid"]["errors"]
    assert order_errors[0]["code"] == OrderErrorCode.PAYMENT_ERROR.name


def test_order_mark_as_paid_with_external_reference_with_payment(
    staff_api_client, permission_manage_orders, order_with_lines, staff_user
):
    transaction_reference = "searchable-id"
    order = order_with_lines
    query = MUTATION_MARK_ORDER_AS_PAID
    assert not order.is_fully_paid()
    order_id = graphene.Node.to_global_id("Order", order.id)
    variables = {"id": order_id, "transaction": transaction_reference}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)

    data = content["data"]["orderMarkAsPaid"]["order"]
    order.refresh_from_db()
    assert data["isPaid"] is True
    assert len(data["events"]) == 1
    assert data["events"][0]["transactionReference"] == transaction_reference
    assert order.is_fully_paid()
    event_order_paid = order.events.first()
    assert event_order_paid.type == order_events.OrderEvents.ORDER_MARKED_AS_PAID
    assert event_order_paid.user == staff_user
    event_reference = event_order_paid.parameters.get("transaction_reference")
    assert event_reference == transaction_reference
    order_payments = order.payments.filter(psp_reference=transaction_reference)
    assert order_payments.count() == 1


@pytest.mark.parametrize(
    "order_mark_as_paid_strategy",
    [MarkAsPaidStrategy.TRANSACTION_FLOW, MarkAsPaidStrategy.PAYMENT_FLOW],
)
def test_order_mark_as_paid_with_payment(
    order_mark_as_paid_strategy,
    staff_api_client,
    permission_manage_orders,
    order_with_lines,
    staff_user,
):
    # given
    order = order_with_lines

    channel = order.channel
    channel.order_mark_as_paid_strategy = order_mark_as_paid_strategy
    channel.save(update_fields=["order_mark_as_paid_strategy"])

    query = MUTATION_MARK_ORDER_AS_PAID
    assert not order.is_fully_paid()
    order_id = graphene.Node.to_global_id("Order", order.id)
    variables = {"id": order_id}

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["orderMarkAsPaid"]["order"]
    order.refresh_from_db()
    assert data["isPaid"] is True is order.is_fully_paid()

    event_order_paid = order.events.first()
    assert event_order_paid.type == order_events.OrderEvents.ORDER_MARKED_AS_PAID
    assert event_order_paid.user == staff_user


@pytest.mark.parametrize(
    "order_mark_as_paid_strategy",
    [MarkAsPaidStrategy.TRANSACTION_FLOW, MarkAsPaidStrategy.PAYMENT_FLOW],
)
def test_order_mark_as_paid_no_billing_address_with_payment(
    order_mark_as_paid_strategy,
    staff_api_client,
    permission_manage_orders,
    order_with_lines,
    staff_user,
):
    # given
    order = order_with_lines
    order_with_lines.billing_address = None
    order_with_lines.save()

    channel = order.channel
    channel.order_mark_as_paid_strategy = order_mark_as_paid_strategy
    channel.save(update_fields=["order_mark_as_paid_strategy"])

    query = MUTATION_MARK_ORDER_AS_PAID
    order_id = graphene.Node.to_global_id("Order", order.id)
    variables = {"id": order_id}

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["orderMarkAsPaid"]["errors"]
    assert data[0]["code"] == OrderErrorCode.BILLING_ADDRESS_NOT_SET.name


def test_draft_order_mark_as_paid_check_price_recalculation_with_payment(
    staff_api_client, permission_manage_orders, order_with_lines, staff_user
):
    # given
    order = order_with_lines
    # we need to change order total and set it as invalidated prices.
    # we couldn't use `order.total.gross` because this test don't use any tax app
    # or plugin.
    expected_total_net = order.total.net
    expected_total = TaxedMoney(net=expected_total_net, gross=expected_total_net)
    order.total = TaxedMoney(net=Money(0, "USD"), gross=Money(0, "USD"))
    order.should_refresh_prices = True
    order.status = OrderStatus.DRAFT
    order.save()
    query = MUTATION_MARK_ORDER_AS_PAID
    order_id = graphene.Node.to_global_id("Order", order.id)
    variables = {"id": order_id}

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["orderMarkAsPaid"]["order"]
    order.refresh_from_db()
    assert order.total == expected_total
    payment = order.payments.get()
    assert payment.total == expected_total_net.amount
    assert data["isPaid"] is True is order.is_fully_paid()
    event_order_paid = order.events.first()
    assert event_order_paid.type == order_events.OrderEvents.ORDER_MARKED_AS_PAID
    assert event_order_paid.user == staff_user


def test_paid_order_mark_as_paid_with_transaction(
    staff_api_client, permission_manage_orders, order_with_lines
):
    # given
    order = order_with_lines
    channel = order.channel
    channel.order_mark_as_paid_strategy = MarkAsPaidStrategy.TRANSACTION_FLOW
    channel.save(update_fields=["order_mark_as_paid_strategy"])

    order.payment_transactions.create(charged_value=order.total.gross.amount)

    query = MUTATION_MARK_ORDER_AS_PAID
    order_id = graphene.Node.to_global_id("Order", order.id)
    variables = {"id": order_id}

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )

    # then
    content = get_graphql_content(response)
    errors = content["data"]["orderMarkAsPaid"]["errors"]
    msg = "Orders with transactions can not be manually marked as paid."
    assert errors[0]["message"] == msg
    assert errors[0]["field"] == "transaction"

    order_errors = content["data"]["orderMarkAsPaid"]["errors"]
    assert order_errors[0]["code"] == OrderErrorCode.TRANSACTION_ERROR.name


def test_order_mark_as_paid_with_external_reference_with_transaction(
    staff_api_client, permission_manage_orders, order_with_lines, staff_user
):
    # given
    order = order_with_lines
    channel = order.channel
    channel.order_mark_as_paid_strategy = MarkAsPaidStrategy.TRANSACTION_FLOW
    channel.save(update_fields=["order_mark_as_paid_strategy"])

    transaction_reference = "searchable-id"
    query = MUTATION_MARK_ORDER_AS_PAID
    assert not order.is_fully_paid()
    order_id = graphene.Node.to_global_id("Order", order.id)
    variables = {"id": order_id, "transaction": transaction_reference}

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )

    # then
    content = get_graphql_content(response)

    data = content["data"]["orderMarkAsPaid"]["order"]
    order.refresh_from_db()
    assert data["isPaid"] is True
    assert len(data["events"]) == 1
    assert data["events"][0]["transactionReference"] == transaction_reference
    assert order.is_fully_paid()
    event_order_paid = order.events.first()
    assert event_order_paid.type == order_events.OrderEvents.ORDER_MARKED_AS_PAID
    assert event_order_paid.user == staff_user
    event_reference = event_order_paid.parameters.get("transaction_reference")
    assert event_reference == transaction_reference
    transactions = order.payment_transactions.filter(
        psp_reference=transaction_reference
    )
    assert transactions.count() == 1


def test_order_mark_as_paid_with_transaction_creates_transaction_event(
    staff_api_client, permission_manage_orders, order_with_lines, staff_user
):
    # given
    order = order_with_lines
    channel = order.channel
    channel.order_mark_as_paid_strategy = MarkAsPaidStrategy.TRANSACTION_FLOW
    channel.save(update_fields=["order_mark_as_paid_strategy"])

    query = MUTATION_MARK_ORDER_AS_PAID
    order_id = graphene.Node.to_global_id("Order", order.id)
    variables = {"id": order_id}

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )

    # then
    get_graphql_content(response)

    order.refresh_from_db()
    transaction = order.payment_transactions.get()
    assert transaction.charged_value == order.total.gross.amount
    transaction_event = transaction.events.filter(
        type=TransactionEventType.CHARGE_SUCCESS
    ).get()
    assert transaction_event.amount_value == order.total.gross.amount


def test_draft_order_mark_as_paid_check_price_recalculation_transaction(
    staff_api_client, permission_manage_orders, order_with_lines, staff_user
):
    # given
    order = order_with_lines
    # we need to change order total and set it as invalidated prices.
    # we couldn't use `order.total.gross` because this test don't use any tax app
    # or plugin.
    expected_total_net = order.total.net
    expected_total = TaxedMoney(net=expected_total_net, gross=expected_total_net)
    order.total = TaxedMoney(net=Money(0, "USD"), gross=Money(0, "USD"))
    order.should_refresh_prices = True
    order.status = OrderStatus.DRAFT
    order.save()

    channel = order.channel
    channel.order_mark_as_paid_strategy = MarkAsPaidStrategy.TRANSACTION_FLOW
    channel.save(update_fields=["order_mark_as_paid_strategy"])

    query = MUTATION_MARK_ORDER_AS_PAID
    order_id = graphene.Node.to_global_id("Order", order.id)
    variables = {"id": order_id}

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)

    # then
    data = content["data"]["orderMarkAsPaid"]["order"]
    assert data["isPaid"] is True is order.is_fully_paid()
    order.refresh_from_db()
    assert order.total == expected_total
    transaction = order.payment_transactions.get()
    assert transaction.charged_value == expected_total_net.amount
    event_order_paid = order.events.first()
    assert event_order_paid.type == order_events.OrderEvents.ORDER_MARKED_AS_PAID
    assert event_order_paid.user == staff_user
