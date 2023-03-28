from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone

from .....payment import TransactionEventType
from .....payment.models import TransactionEvent
from .....payment.transaction_item_calculations import recalculate_transaction_amounts
from ....core.enums import TransactionEventReportErrorCode
from ....core.utils import to_global_id_or_none
from ....order.enums import OrderAuthorizeStatusEnum, OrderChargeStatusEnum
from ....tests.utils import assert_no_permission, get_graphql_content
from ...enums import TransactionActionEnum, TransactionEventTypeEnum

TEST_SERVER_DOMAIN = "testserver.com"

MUTATION_DATA_FRAGMENT = """
fragment TransactionEventData on TransactionEventReport {
    alreadyProcessed
    transaction {
        id
        actions
        events {
            id
        }
    }
    transactionEvent {
        id
        createdAt
        pspReference
        message
        externalUrl
        amount {
            currency
            amount
        }
        type
        createdBy {
        ... on User {
            id
        }
        ... on App {
            id
        }
        }
    }
    errors {
        field
        code
    }
}
"""


def test_transaction_event_report_by_app(
    transaction_item_generator,
    app_api_client,
    permission_manage_payments,
):
    # given
    transaction = transaction_item_generator(
        app=app_api_client.app, authorized_value=Decimal("10")
    )
    event_time = timezone.now()
    external_url = f"http://{TEST_SERVER_DOMAIN}/external-url"
    message = "Sucesfull charge"
    psp_reference = "111-abc"
    amount = Decimal("11.00")
    transaction_id = to_global_id_or_none(transaction)
    variables = {
        "id": transaction_id,
        "type": TransactionEventTypeEnum.CHARGE_SUCCESS.name,
        "amount": amount,
        "pspReference": psp_reference,
        "time": event_time.isoformat(),
        "externalUrl": external_url,
        "message": message,
        "availableActions": [TransactionActionEnum.REFUND.name],
    }
    query = (
        MUTATION_DATA_FRAGMENT
        + """
    mutation TransactionEventReport(
        $id: ID!
        $type: TransactionEventTypeEnum!
        $amount: PositiveDecimal!
        $pspReference: String!
        $time: DateTime
        $externalUrl: String
        $message: String
        $availableActions: [TransactionActionEnum!]!
    ) {
        transactionEventReport(
            id: $id
            type: $type
            amount: $amount
            pspReference: $pspReference
            time: $time
            externalUrl: $externalUrl
            message: $message
            availableActions: $availableActions
        ) {
            ...TransactionEventData
        }
    }
    """
    )
    # when
    response = app_api_client.post_graphql(
        query, variables, permissions=[permission_manage_payments]
    )

    # then
    response = get_graphql_content(response)
    transaction_report_data = response["data"]["transactionEventReport"]
    assert transaction_report_data["alreadyProcessed"] is False

    event = TransactionEvent.objects.filter(
        type=TransactionEventType.CHARGE_SUCCESS
    ).first()
    assert event
    assert event.psp_reference == psp_reference
    assert event.type == TransactionEventTypeEnum.CHARGE_SUCCESS.value
    assert event.amount_value == amount
    assert event.currency == transaction.currency
    assert event.created_at == event_time
    assert event.external_url == external_url
    assert event.transaction == transaction
    assert event.app_identifier == app_api_client.app.identifier
    assert event.app == app_api_client.app
    assert event.user is None


def test_transaction_event_report_by_user(
    staff_api_client, permission_manage_payments, staff_user, transaction_item_generator
):
    # given
    transaction = transaction_item_generator(user=staff_user)
    event_time = timezone.now()
    external_url = f"http://{TEST_SERVER_DOMAIN}/external-url"
    message = "Sucesfull charge"
    psp_reference = "111-abc"
    amount = Decimal("11.00")
    transaction_id = to_global_id_or_none(transaction)
    variables = {
        "id": transaction_id,
        "type": TransactionEventTypeEnum.CHARGE_SUCCESS.name,
        "amount": amount,
        "pspReference": psp_reference,
        "time": event_time.isoformat(),
        "externalUrl": external_url,
        "message": message,
        "availableActions": [TransactionActionEnum.CANCEL.name],
    }
    query = (
        MUTATION_DATA_FRAGMENT
        + """
    mutation TransactionEventReport(
        $id: ID!
        $type: TransactionEventTypeEnum!
        $amount: PositiveDecimal!
        $pspReference: String!
        $time: DateTime
        $externalUrl: String
        $message: String
        $availableActions: [TransactionActionEnum!]!
    ) {
        transactionEventReport(
            id: $id
            type: $type
            amount: $amount
            pspReference: $pspReference
            time: $time
            externalUrl: $externalUrl
            message: $message
            availableActions: $availableActions
        ) {
            ...TransactionEventData
        }
    }
    """
    )
    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_payments]
    )

    # then
    get_graphql_content(response)

    event = TransactionEvent.objects.get()
    assert event.psp_reference == psp_reference
    assert event.type == TransactionEventTypeEnum.CHARGE_SUCCESS.value
    assert event.amount_value == amount
    assert event.currency == transaction.currency
    assert event.created_at == event_time
    assert event.external_url == external_url
    assert event.transaction == transaction
    assert event.app_identifier is None
    assert event.app is None
    assert event.user == staff_api_client.user

    transaction.refresh_from_db()
    assert transaction.available_actions == [TransactionActionEnum.CANCEL.value]


def test_transaction_event_report_no_permission(
    transaction_item_created_by_app,
    app_api_client,
):
    # given
    transaction_id = to_global_id_or_none(transaction_item_created_by_app)
    variables = {
        "id": transaction_id,
        "type": TransactionEventTypeEnum.CHARGE_SUCCESS.name,
        "amount": Decimal("11.00"),
        "pspReference": "111-abc",
    }
    query = (
        MUTATION_DATA_FRAGMENT
        + """
    mutation TransactionEventReport(
        $id: ID!
        $type: TransactionEventTypeEnum!
        $amount: PositiveDecimal!
        $pspReference: String!
    ) {
        transactionEventReport(
            id: $id
            type: $type
            amount: $amount
            pspReference: $pspReference
        ) {
            ...TransactionEventData
        }
    }
    """
    )
    # when
    response = app_api_client.post_graphql(
        query,
        variables,
    )

    # then
    assert_no_permission(response)


def test_transaction_event_report_called_by_non_app_owner(
    transaction_item_created_by_app, app_api_client, permission_manage_payments
):
    # given
    second_app = app_api_client.app
    second_app.pk = None
    second_app.identifier = "different-identifier"
    second_app.save()
    transaction_item_created_by_app.app_identifier = second_app.identifier
    transaction_item_created_by_app.app = None
    transaction_item_created_by_app.save(update_fields=["app_identifier", "app"])

    transaction_id = to_global_id_or_none(transaction_item_created_by_app)
    variables = {
        "id": transaction_id,
        "type": TransactionEventTypeEnum.CHARGE_SUCCESS.name,
        "amount": Decimal("11.00"),
        "pspReference": "111-abc",
    }
    query = (
        MUTATION_DATA_FRAGMENT
        + """
    mutation TransactionEventReport(
        $id: ID!
        $type: TransactionEventTypeEnum!
        $amount: PositiveDecimal!
        $pspReference: String!
    ) {
        transactionEventReport(
            id: $id
            type: $type
            amount: $amount
            pspReference: $pspReference
        ) {
            ...TransactionEventData
        }
    }
    """
    )
    # when
    response = app_api_client.post_graphql(
        query, variables, permissions=[permission_manage_payments]
    )

    # then
    assert_no_permission(response)


def test_transaction_event_report_called_by_non_user_owner(
    transaction_item_created_by_app, staff_api_client, permission_manage_payments
):
    # given
    transaction_id = to_global_id_or_none(transaction_item_created_by_app)
    variables = {
        "id": transaction_id,
        "type": TransactionEventTypeEnum.CHARGE_SUCCESS.name,
        "amount": Decimal("11.00"),
        "pspReference": "111-abc",
    }
    query = (
        MUTATION_DATA_FRAGMENT
        + """
    mutation TransactionEventReport(
        $id: ID!
        $type: TransactionEventTypeEnum!
        $amount: PositiveDecimal!
        $pspReference: String!
    ) {
        transactionEventReport(
            id: $id
            type: $type
            amount: $amount
            pspReference: $pspReference
        ) {
            ...TransactionEventData
        }
    }
    """
    )
    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_payments]
    )

    # then
    assert_no_permission(response)


def test_transaction_event_report_event_already_exists(
    transaction_item_generator, app_api_client, permission_manage_payments, app
):
    # given
    event_time = timezone.now()
    external_url = f"http://{TEST_SERVER_DOMAIN}/external-url"
    message = "Sucesfull charge"
    psp_reference = "111-abc"
    amount = Decimal("11.00")
    event_type = TransactionEventTypeEnum.CHARGE_SUCCESS
    transaction = transaction_item_generator(app=app, charged_value=amount)
    transaction.events.update(
        psp_reference=psp_reference,
    )

    already_existing_event = transaction.events.filter(
        type=TransactionEventType.CHARGE_SUCCESS
    ).get()
    transaction_id = to_global_id_or_none(transaction)
    variables = {
        "id": transaction_id,
        "type": event_type.name,
        "amount": amount,
        "pspReference": psp_reference,
        "time": event_time.isoformat(),
        "externalUrl": external_url,
        "message": message,
        "availableActions": [TransactionActionEnum.REFUND.name],
    }

    query = (
        MUTATION_DATA_FRAGMENT
        + """
    mutation TransactionEventReport(
        $id: ID!
        $type: TransactionEventTypeEnum!
        $amount: PositiveDecimal!
        $pspReference: String!
        $time: DateTime
        $externalUrl: String
        $message: String
        $availableActions: [TransactionActionEnum!]!
    ) {
        transactionEventReport(
            id: $id
            type: $type
            amount: $amount
            pspReference: $pspReference
            time: $time
            externalUrl: $externalUrl
            message: $message
            availableActions: $availableActions
        ) {
            ...TransactionEventData
        }
    }
    """
    )
    # when
    response = app_api_client.post_graphql(
        query, variables, permissions=[permission_manage_payments]
    )

    # then
    response = get_graphql_content(response)
    transaction_report_data = response["data"]["transactionEventReport"]
    assert transaction_report_data["alreadyProcessed"] is True
    transaction_event_data = transaction_report_data["transactionEvent"]
    assert transaction_event_data["id"] == to_global_id_or_none(already_existing_event)

    assert (
        TransactionEvent.objects.filter(
            type=TransactionEventType.CHARGE_SUCCESS
        ).count()
        == 1
    )


def test_transaction_event_report_incorrect_amount_for_already_existing(
    app_api_client, permission_manage_payments, transaction_item_generator, app
):
    # given
    event_time = timezone.now()
    external_url = f"http://{TEST_SERVER_DOMAIN}/external-url"
    message = "Sucesfull charge"
    psp_reference = "111-abc"
    already_existing_amount = Decimal("11.00")
    new_amount = Decimal("12.00")
    event_type = TransactionEventTypeEnum.CHARGE_SUCCESS
    transaction = transaction_item_generator(
        app=app, charged_value=already_existing_amount
    )
    transaction.events.update(
        psp_reference=psp_reference,
    )
    transaction_id = to_global_id_or_none(transaction)

    variables = {
        "id": transaction_id,
        "type": event_type.name,
        "amount": new_amount,
        "pspReference": psp_reference,
        "time": event_time.isoformat(),
        "externalUrl": external_url,
        "message": message,
        "availableActions": [TransactionActionEnum.REFUND.name],
    }

    query = (
        MUTATION_DATA_FRAGMENT
        + """
    mutation TransactionEventReport(
        $id: ID!
        $type: TransactionEventTypeEnum!
        $amount: PositiveDecimal!
        $pspReference: String!
        $time: DateTime
        $externalUrl: String
        $message: String
        $availableActions: [TransactionActionEnum!]!
    ) {
        transactionEventReport(
            id: $id
            type: $type
            amount: $amount
            pspReference: $pspReference
            time: $time
            externalUrl: $externalUrl
            message: $message
            availableActions: $availableActions
        ) {
            ...TransactionEventData
        }
    }
    """
    )
    # when
    response = app_api_client.post_graphql(
        query, variables, permissions=[permission_manage_payments]
    )

    # then
    response = get_graphql_content(response)
    assert already_existing_amount != new_amount
    transaction_report_data = response["data"]["transactionEventReport"]

    assert len(transaction_report_data["errors"]) == 1
    error = transaction_report_data["errors"][0]
    assert error["code"] == TransactionEventReportErrorCode.INCORRECT_DETAILS.name
    assert error["field"] == "pspReference"

    assert TransactionEvent.objects.count() == 2
    event = TransactionEvent.objects.filter(
        type=TransactionEventTypeEnum.CHARGE_FAILURE.value
    ).first()
    assert event
    assert event.include_in_calculations is False


@patch(
    "saleor.graphql.payment.mutations.recalculate_transaction_amounts",
    wraps=recalculate_transaction_amounts,
)
def test_transaction_event_report_calls_amount_recalculations(
    mocked_recalculation,
    transaction_item_generator,
    app_api_client,
    permission_manage_payments,
):
    # given
    event_time = timezone.now()
    external_url = f"http://{TEST_SERVER_DOMAIN}/external-url"
    message = "Sucesfull charge"
    psp_reference = "111-abc"
    amount = Decimal("11.00")
    transaction = transaction_item_generator(app=app_api_client.app)
    transaction_id = to_global_id_or_none(transaction)
    variables = {
        "id": transaction_id,
        "type": TransactionEventTypeEnum.CHARGE_SUCCESS.name,
        "amount": amount,
        "pspReference": psp_reference,
        "time": event_time.isoformat(),
        "externalUrl": external_url,
        "message": message,
        "availableActions": [TransactionActionEnum.REFUND.name],
    }
    query = (
        MUTATION_DATA_FRAGMENT
        + """
    mutation TransactionEventReport(
        $id: ID!
        $type: TransactionEventTypeEnum!
        $amount: PositiveDecimal!
        $pspReference: String!
        $time: DateTime
        $externalUrl: String
        $message: String
        $availableActions: [TransactionActionEnum!]!
    ) {
        transactionEventReport(
            id: $id
            type: $type
            amount: $amount
            pspReference: $pspReference
            time: $time
            externalUrl: $externalUrl
            message: $message
            availableActions: $availableActions
        ) {
            ...TransactionEventData
        }
    }
    """
    )
    # when
    app_api_client.post_graphql(
        query, variables, permissions=[permission_manage_payments]
    )

    # then
    mocked_recalculation.assert_called_once_with(transaction)
    transaction.refresh_from_db()
    assert transaction.charged_value == amount


def test_transaction_event_updates_order_total_charged(
    transaction_item_generator,
    app_api_client,
    permission_manage_payments,
    order_with_lines,
):
    # given
    order = order_with_lines
    current_charged_value = Decimal("20")
    psp_reference = "111-abc"
    amount = Decimal("11.00")
    transaction = transaction_item_generator(app=app_api_client.app, order_id=order.pk)
    transaction_item_generator(
        app=app_api_client.app,
        order_id=order.pk,
        charged_value=current_charged_value,
    )
    transaction_id = to_global_id_or_none(transaction)
    variables = {
        "id": transaction_id,
        "type": TransactionEventTypeEnum.CHARGE_SUCCESS.name,
        "amount": amount,
        "pspReference": psp_reference,
    }
    query = (
        MUTATION_DATA_FRAGMENT
        + """
    mutation TransactionEventReport(
        $id: ID!
        $type: TransactionEventTypeEnum!
        $amount: PositiveDecimal!
        $pspReference: String!
    ) {
        transactionEventReport(
            id: $id
            type: $type
            amount: $amount
            pspReference: $pspReference
        ) {
            ...TransactionEventData
        }
    }
    """
    )
    # when
    response = app_api_client.post_graphql(
        query, variables, permissions=[permission_manage_payments]
    )

    # then
    get_graphql_content(response)
    order.refresh_from_db()

    assert order.total_charged.amount == current_charged_value + amount
    assert order.charge_status == OrderChargeStatusEnum.PARTIAL.value


def test_transaction_event_updates_order_total_authorized(
    app_api_client,
    permission_manage_payments,
    order_with_lines,
    transaction_item_generator,
):
    # given
    order = order_with_lines
    psp_reference = "111-abc"
    amount = Decimal("11.00")
    transaction = transaction_item_generator(app=app_api_client.app, order_id=order.pk)
    transaction_item_generator(
        app=app_api_client.app,
        order_id=order.pk,
        authorized_value=order.total.gross.amount,
    )
    transaction_id = to_global_id_or_none(transaction)
    variables = {
        "id": transaction_id,
        "type": TransactionEventTypeEnum.AUTHORIZATION_SUCCESS.name,
        "amount": amount,
        "pspReference": psp_reference,
    }
    query = (
        MUTATION_DATA_FRAGMENT
        + """
    mutation TransactionEventReport(
        $id: ID!
        $type: TransactionEventTypeEnum!
        $amount: PositiveDecimal!
        $pspReference: String!
    ) {
        transactionEventReport(
            id: $id
            type: $type
            amount: $amount
            pspReference: $pspReference
        ) {
            ...TransactionEventData
        }
    }
    """
    )
    # when
    response = app_api_client.post_graphql(
        query, variables, permissions=[permission_manage_payments]
    )

    # then
    get_graphql_content(response)
    order.refresh_from_db()

    assert order.total_authorized.amount == order.total.gross.amount + amount
    assert order.authorize_status == OrderAuthorizeStatusEnum.FULL.value


def test_transaction_event_updates_search_vector(
    app_api_client,
    permission_manage_payments,
    order_with_lines,
    transaction_item_generator,
):
    # given
    order = order_with_lines
    psp_reference = "111-abc"
    amount = Decimal("11.00")
    transaction = transaction_item_generator(app=app_api_client.app, order_id=order.pk)
    transaction_item_generator(
        app=app_api_client.app,
        order_id=order.pk,
        authorized_value=order.total.gross.amount,
    )
    transaction_id = to_global_id_or_none(transaction)
    variables = {
        "id": transaction_id,
        "type": TransactionEventTypeEnum.AUTHORIZATION_SUCCESS.name,
        "amount": amount,
        "pspReference": psp_reference,
    }
    query = (
        MUTATION_DATA_FRAGMENT
        + """
    mutation TransactionEventReport(
        $id: ID!
        $type: TransactionEventTypeEnum!
        $amount: PositiveDecimal!
        $pspReference: String!
    ) {
        transactionEventReport(
            id: $id
            type: $type
            amount: $amount
            pspReference: $pspReference
        ) {
            ...TransactionEventData
        }
    }
    """
    )
    # when
    response = app_api_client.post_graphql(
        query, variables, permissions=[permission_manage_payments]
    )

    # then
    get_graphql_content(response)
    order.refresh_from_db()

    assert order.search_vector


def test_transaction_event_report_authorize_event_already_exists(
    app_api_client, permission_manage_payments, transaction_item_generator
):
    # given
    event_time = timezone.now()
    external_url = f"http://{TEST_SERVER_DOMAIN}/external-url"
    message = "Sucesfull charge"
    psp_reference = "111-abc"
    amount = Decimal("11.00")
    event_type = TransactionEventTypeEnum.AUTHORIZATION_SUCCESS
    transaction = transaction_item_generator(
        app=app_api_client.app,
        authorized_value=amount + Decimal(1),
    )
    transaction.events.update(
        psp_reference="Different psp reference",
    )
    transaction_id = to_global_id_or_none(transaction)
    variables = {
        "id": transaction_id,
        "type": event_type.name,
        "amount": amount,
        "pspReference": psp_reference,
        "time": event_time.isoformat(),
        "externalUrl": external_url,
        "message": message,
        "availableActions": [TransactionActionEnum.REFUND.name],
    }

    query = (
        MUTATION_DATA_FRAGMENT
        + """
    mutation TransactionEventReport(
        $id: ID!
        $type: TransactionEventTypeEnum!
        $amount: PositiveDecimal!
        $pspReference: String!
        $time: DateTime
        $externalUrl: String
        $message: String
        $availableActions: [TransactionActionEnum!]!
    ) {
        transactionEventReport(
            id: $id
            type: $type
            amount: $amount
            pspReference: $pspReference
            time: $time
            externalUrl: $externalUrl
            message: $message
            availableActions: $availableActions
        ) {
            ...TransactionEventData
        }
    }
    """
    )
    # when
    response = app_api_client.post_graphql(
        query, variables, permissions=[permission_manage_payments]
    )

    # then
    response = get_graphql_content(response)
    transaction_report_data = response["data"]["transactionEventReport"]
    assert len(transaction_report_data["errors"]) == 1
    assert transaction_report_data["errors"][0]["field"] == "type"
    assert (
        transaction_report_data["errors"][0]["code"]
        == TransactionEventReportErrorCode.ALREADY_EXISTS.name
    )

    assert TransactionEvent.objects.count() == 2
    event = TransactionEvent.objects.filter(
        type=TransactionEventTypeEnum.AUTHORIZATION_FAILURE.value
    ).first()
    assert event
    assert event.include_in_calculations is False
