from unittest.mock import patch

import graphene
import pytest

from saleor.core.permissions import OrderPermissions
from saleor.order.events import OrderEvents
from saleor.order.models import FulfillmentStatus
from saleor.warehouse.models import Allocation
from tests.api.utils import assert_no_permission, get_graphql_content

CREATE_FULFILLMENT_QUERY = """
    mutation fulfillOrder(
        $order: ID, $lines: [FulfillmentLineInput]!, $tracking: String,
        $notify: Boolean
    ) {
        orderFulfillmentCreate(
            order: $order,
            input: {
                lines: $lines, trackingNumber: $tracking,
                notifyCustomer: $notify}
        ) {
            errors {
                field
                message
            }
            fulfillment {
                fulfillmentOrder
                status
                trackingNumber
            lines {
                id
            }
        }
    }
}
"""


@patch("saleor.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillment(
    mock_email_fulfillment,
    staff_api_client,
    order_with_lines,
    staff_user,
    permission_manage_orders,
):
    order = order_with_lines
    query = CREATE_FULFILLMENT_QUERY
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line = order.lines.first()
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    tracking = "Flames tracking"
    variables = {
        "order": order_id,
        "lines": [{"orderLineId": order_line_id, "quantity": 1}],
        "tracking": tracking,
        "notify": True,
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentCreate"]["fulfillment"]
    assert data["fulfillmentOrder"] == 1
    assert data["status"] == FulfillmentStatus.FULFILLED.upper()
    assert data["trackingNumber"] == tracking
    assert len(data["lines"]) == 1

    assert mock_email_fulfillment.call_count == 1


@patch("saleor.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillment_with_empty_quantity(
    mock_send_fulfillment_confirmation,
    staff_api_client,
    order_with_lines,
    staff_user,
    permission_manage_orders,
):
    order = order_with_lines
    query = CREATE_FULFILLMENT_QUERY
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_lines = order.lines.all()
    order_line_ids = [
        graphene.Node.to_global_id("OrderLine", order_line.id)
        for order_line in order_lines
    ]
    tracking = "Flames tracking"
    assert not order.events.all()
    variables = {
        "order": order_id,
        "lines": [
            {"orderLineId": order_line_id, "quantity": 1}
            for order_line_id in order_line_ids
        ],
        "tracking": tracking,
        "notify": True,
    }
    variables["lines"][0]["quantity"] = 0
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentCreate"]["fulfillment"]
    assert data["fulfillmentOrder"] == 1
    assert data["status"] == FulfillmentStatus.FULFILLED.upper()

    assert mock_send_fulfillment_confirmation.called


@pytest.mark.parametrize(
    "quantity, error_message, error_field",
    (
        (0, "Total quantity must be larger than 0.", "lines"),
        (100, "Only 3 items remaining to fulfill:", "orderLineId"),
    ),
)
def test_create_fulfillment_not_sufficient_quantity(
    staff_api_client,
    order_with_lines,
    staff_user,
    quantity,
    error_message,
    error_field,
    permission_manage_orders,
):
    query = CREATE_FULFILLMENT_QUERY
    order_line = order_with_lines.lines.first()
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    variables = {
        "order": graphene.Node.to_global_id("Order", order_with_lines.id),
        "lines": [{"orderLineId": order_line_id, "quantity": quantity}],
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentCreate"]
    assert data["errors"]
    assert data["errors"][0]["field"] == error_field
    assert error_message in data["errors"][0]["message"]


def test_create_fulfillment_with_invalid_input(
    staff_api_client, order_with_lines, permission_manage_orders
):
    query = CREATE_FULFILLMENT_QUERY
    variables = {
        "order": graphene.Node.to_global_id("Order", order_with_lines.id),
        "lines": [{"orderLineId": "fake-orderline-id", "quantity": 1}],
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentCreate"]
    assert data["errors"]
    assert data["errors"][0]["field"] == "lines"
    assert data["errors"][0]["message"] == (
        "Could not resolve to a node with the global id list"
        " of '['fake-orderline-id']'."
    )


@patch("saleor.order.emails.send_fulfillment_update.delay")
def test_fulfillment_update_tracking(
    send_fulfillment_update_mock,
    staff_api_client,
    fulfillment,
    permission_manage_orders,
):
    query = """
    mutation updateFulfillment($id: ID!, $tracking: String) {
            orderFulfillmentUpdateTracking(
                id: $id, input: {trackingNumber: $tracking}) {
                    fulfillment {
                        trackingNumber
                    }
                }
        }
    """
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    tracking = "stationary tracking"
    variables = {"id": fulfillment_id, "tracking": tracking}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentUpdateTracking"]["fulfillment"]
    assert data["trackingNumber"] == tracking
    send_fulfillment_update_mock.assert_not_called()


FULFILLMENT_UPDATE_TRACKING_WITH_SEND_NOTIFICATION_QUERY = """
    mutation updateFulfillment($id: ID!, $tracking: String, $notifyCustomer: Boolean) {
            orderFulfillmentUpdateTracking(
                id: $id
                input: {trackingNumber: $tracking, notifyCustomer: $notifyCustomer}) {
                    fulfillment {
                        trackingNumber
                    }
                }
        }
    """


@patch("saleor.order.emails.send_fulfillment_update.delay")
def test_fulfillment_update_tracking_send_notification_true(
    send_fulfillment_update_mock,
    staff_api_client,
    fulfillment,
    permission_manage_orders,
):
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    tracking = "stationary tracking"
    variables = {"id": fulfillment_id, "tracking": tracking, "notifyCustomer": True}
    response = staff_api_client.post_graphql(
        FULFILLMENT_UPDATE_TRACKING_WITH_SEND_NOTIFICATION_QUERY,
        variables,
        permissions=[permission_manage_orders],
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentUpdateTracking"]["fulfillment"]
    assert data["trackingNumber"] == tracking
    send_fulfillment_update_mock.assert_called_once_with(
        fulfillment.order.pk, fulfillment.pk
    )


@patch("saleor.order.emails.send_fulfillment_update.delay")
def test_fulfillment_update_tracking_send_notification_false(
    send_fulfillment_update_mock,
    staff_api_client,
    fulfillment,
    permission_manage_orders,
):
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    tracking = "stationary tracking"
    variables = {"id": fulfillment_id, "tracking": tracking, "notifyCustomer": False}
    response = staff_api_client.post_graphql(
        FULFILLMENT_UPDATE_TRACKING_WITH_SEND_NOTIFICATION_QUERY,
        variables,
        permissions=[permission_manage_orders],
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentUpdateTracking"]["fulfillment"]
    assert data["trackingNumber"] == tracking
    send_fulfillment_update_mock.assert_not_called()


def test_cancel_fulfillment_restock_items(
    staff_api_client, fulfillment, staff_user, permission_manage_orders
):
    query = """
    mutation cancelFulfillment($id: ID!, $restock: Boolean) {
            orderFulfillmentCancel(id: $id, input: {restock: $restock}) {
                    fulfillment {
                        status
                    }
                }
        }
    """
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    variables = {"id": fulfillment_id, "restock": True}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentCancel"]["fulfillment"]
    assert data["status"] == FulfillmentStatus.CANCELED.upper()
    event_cancelled, event_restocked_items = fulfillment.order.events.all()
    assert event_cancelled.type == (OrderEvents.FULFILLMENT_CANCELED)
    assert event_cancelled.parameters == {"composed_id": fulfillment.composed_id}
    assert event_cancelled.user == staff_user

    assert event_restocked_items.type == (OrderEvents.FULFILLMENT_RESTOCKED_ITEMS)
    assert event_restocked_items.parameters == {
        "quantity": fulfillment.get_total_quantity()
    }
    assert event_restocked_items.user == staff_user


def test_cancel_fulfillment(
    staff_api_client, fulfillment, staff_user, permission_manage_orders
):
    query = """
    mutation cancelFulfillment($id: ID!, $restock: Boolean) {
            orderFulfillmentCancel(id: $id, input: {restock: $restock}) {
                    fulfillment {
                        status
                    }
                }
        }
    """
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    variables = {"id": fulfillment_id, "restock": False}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentCancel"]["fulfillment"]
    assert data["status"] == FulfillmentStatus.CANCELED.upper()
    event_cancel_fulfillment = fulfillment.order.events.get()
    assert event_cancel_fulfillment.type == (OrderEvents.FULFILLMENT_CANCELED)
    assert event_cancel_fulfillment.parameters == {
        "composed_id": fulfillment.composed_id
    }
    assert event_cancel_fulfillment.user == staff_user


@patch("saleor.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_digital_fulfillment(
    mock_email_fulfillment,
    digital_content,
    staff_api_client,
    order_with_lines,
    staff_user,
    permission_manage_orders,
):
    order = order_with_lines
    query = CREATE_FULFILLMENT_QUERY
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line = order.lines.first()
    order_line.variant = digital_content.product_variant
    order_line.save()

    stock = digital_content.product_variant.stocks.first()
    Allocation.objects.create(
        order_line=order_line, stock=stock, quantity_allocated=order_line.quantity
    )

    second_line = order.lines.last()
    first_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    second_line_id = graphene.Node.to_global_id("OrderLine", second_line.id)

    tracking = "Flames tracking"
    variables = {
        "order": order_id,
        "lines": [
            {"orderLineId": first_line_id, "quantity": 1},
            {"orderLineId": second_line_id, "quantity": 1},
        ],
        "tracking": tracking,
        "notify": True,
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    get_graphql_content(response)

    assert mock_email_fulfillment.call_count == 1


@pytest.fixture
def update_metadata_mutation():
    return """
        mutation UpdateMeta($id: ID!, $input: MetaInput!){
            orderFulfillmentUpdateMeta(id: $id, input: $input) {
                errors {
                    field
                    message
                }
            }
        }
    """


@pytest.fixture
def update_private_metadata_mutation():
    return """
        mutation UpdatePrivateMeta($id: ID!, $input: MetaInput!){
            orderFulfillmentUpdatePrivateMeta(id: $id, input: $input) {
                errors {
                    field
                    message
                }
            }
        }
    """


@pytest.fixture
def clear_metadata_mutation():
    return """
        mutation fulfillmentClearMeta($id: ID!, $input: MetaPath!) {
            orderFulfillmentClearMeta(id: $id, input: $input) {
                errors {
                    message
                }
            }
        }
    """


@pytest.fixture
def clear_private_metadata_mutation():
    return """
        mutation fulfillmentClearPrivateMeta($id: ID!, $input: MetaPath!) {
            orderFulfillmentClearPrivateMeta(id: $id, input: $input) {
                errors {
                    message
                }
            }
        }
    """


@pytest.fixture
def clear_meta_variables(fulfillment):
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    return {
        "id": fulfillment_id,
        "input": {"namespace": "", "clientName": "", "key": "foo"},
    }


@pytest.fixture
def update_metadata_variables(staff_user, fulfillment):
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    return {
        "id": fulfillment_id,
        "input": {
            "namespace": "",
            "clientName": "",
            "key": str(staff_user),
            "value": "bar",
        },
    }


def test_fulfillment_update_metadata_user_has_no_permision(
    staff_api_client, staff_user, update_metadata_mutation, update_metadata_variables
):
    assert not staff_user.has_perm(OrderPermissions.MANAGE_ORDERS)

    response = staff_api_client.post_graphql(
        update_metadata_mutation,
        update_metadata_variables,
        permissions=[],
        check_no_permissions=False,
    )
    assert_no_permission(response)


def test_fulfillment_update_metadata_user_has_permission(
    staff_api_client,
    staff_user,
    permission_manage_orders,
    fulfillment,
    update_metadata_mutation,
    update_metadata_variables,
):
    staff_user.user_permissions.add(permission_manage_orders)
    assert staff_user.has_perm(OrderPermissions.MANAGE_ORDERS)
    response = staff_api_client.post_graphql(
        update_metadata_mutation,
        update_metadata_variables,
        permissions=[permission_manage_orders],
        check_no_permissions=False,
    )
    assert response.status_code == 200
    content = get_graphql_content(response)
    errors = content["data"]["orderFulfillmentUpdateMeta"]["errors"]
    assert len(errors) == 0
    fulfillment.refresh_from_db()
    assert fulfillment.metadata == {str(staff_user): "bar"}


def test_fulfillment_update_private_metadata_user_has_no_permission(
    staff_api_client,
    staff_user,
    update_private_metadata_mutation,
    update_metadata_variables,
):
    assert not staff_user.has_perm(OrderPermissions.MANAGE_ORDERS)

    response = staff_api_client.post_graphql(
        update_private_metadata_mutation,
        update_metadata_variables,
        permissions=[],
        check_no_permissions=False,
    )
    assert_no_permission(response)


def test_fulfillment_update_private_metadata_user_has_permission(
    staff_api_client,
    staff_user,
    permission_manage_orders,
    fulfillment,
    update_private_metadata_mutation,
    update_metadata_variables,
):
    staff_user.user_permissions.add(permission_manage_orders)
    assert staff_user.has_perm(OrderPermissions.MANAGE_ORDERS)
    response = staff_api_client.post_graphql(
        update_private_metadata_mutation,
        update_metadata_variables,
        permissions=[permission_manage_orders],
        check_no_permissions=False,
    )
    assert response.status_code == 200
    content = get_graphql_content(response)
    errors = content["data"]["orderFulfillmentUpdatePrivateMeta"]["errors"]
    assert len(errors) == 0
    fulfillment.refresh_from_db()
    assert fulfillment.private_metadata == {str(staff_user): "bar"}


def test_fulfillment_clear_meta_user_has_no_permission(
    staff_api_client,
    staff_user,
    fulfillment,
    clear_meta_variables,
    clear_metadata_mutation,
):
    assert not staff_user.has_perm(OrderPermissions.MANAGE_ORDERS)
    fulfillment.store_value_in_metadata(items={"foo": "bar"})
    fulfillment.save()
    response = staff_api_client.post_graphql(
        clear_metadata_mutation, clear_meta_variables
    )
    assert_no_permission(response)


def test_fulfillment_clear_meta_user_has_permission(
    staff_api_client,
    staff_user,
    permission_manage_orders,
    fulfillment,
    clear_meta_variables,
    clear_metadata_mutation,
):
    staff_user.user_permissions.add(permission_manage_orders)
    assert staff_user.has_perm(OrderPermissions.MANAGE_ORDERS)
    fulfillment.store_value_in_metadata(items={"foo": "bar"})
    fulfillment.save()
    fulfillment.refresh_from_db()
    response = staff_api_client.post_graphql(
        clear_metadata_mutation, clear_meta_variables
    )
    assert response.status_code == 200
    content = get_graphql_content(response)
    assert content.get("errors") is None
    fulfillment.refresh_from_db()
    assert not fulfillment.get_value_from_metadata(key="foo")


def test_fulfillment_clear_private_meta_user_has_no_permission(
    staff_api_client,
    staff_user,
    fulfillment,
    clear_meta_variables,
    clear_private_metadata_mutation,
):
    assert not staff_user.has_perm(OrderPermissions.MANAGE_ORDERS)
    fulfillment.store_value_in_private_metadata(items={"foo": "bar"})
    fulfillment.save()
    response = staff_api_client.post_graphql(
        clear_private_metadata_mutation, clear_meta_variables
    )
    assert_no_permission(response)


def test_fulfillment_clear_private_meta_user_has_permission(
    staff_api_client,
    staff_user,
    permission_manage_orders,
    fulfillment,
    clear_meta_variables,
    clear_private_metadata_mutation,
):
    staff_user.user_permissions.add(permission_manage_orders)
    assert staff_user.has_perm(OrderPermissions.MANAGE_ORDERS)
    fulfillment.store_value_in_private_metadata(items={"foo": "bar"})
    fulfillment.save()
    fulfillment.refresh_from_db()
    response = staff_api_client.post_graphql(
        clear_private_metadata_mutation, clear_meta_variables
    )
    assert response.status_code == 200
    content = get_graphql_content(response)
    assert content.get("errors") is None
    fulfillment.refresh_from_db()
    assert not fulfillment.get_value_from_private_metadata(key="foo")
