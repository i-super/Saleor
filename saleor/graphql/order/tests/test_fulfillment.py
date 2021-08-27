from unittest.mock import ANY, patch

import graphene
import pytest

from ....core.exceptions import InsufficientStock, InsufficientStockData
from ....giftcard import GiftCardEvents
from ....giftcard.models import GiftCard, GiftCardEvent
from ....order import OrderStatus
from ....order.error_codes import OrderErrorCode
from ....order.events import OrderEvents
from ....order.models import Fulfillment, FulfillmentStatus
from ....warehouse.models import Allocation, Stock
from ...tests.utils import assert_no_permission, get_graphql_content

ORDER_FULFILL_QUERY = """
    mutation fulfillOrder(
        $order: ID, $input: OrderFulfillInput!
    ) {
        orderFulfill(
            order: $order,
            input: $input
        ) {
            errors {
                field
                code
                message
                warehouse
                orderLines
            }
        }
    }
"""


@patch("saleor.plugins.manager.PluginsManager.product_variant_out_of_stock")
def test_order_fulfill_with_out_of_stock_webhook(
    product_variant_out_of_stock_webhooks,
    staff_api_client,
    order_with_lines,
    permission_manage_orders,
    warehouse,
):
    order = order_with_lines

    query = ORDER_FULFILL_QUERY
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line, order_line2 = order.lines.all()
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    order_line2_id = graphene.Node.to_global_id("OrderLine", order_line2.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "order": order_id,
        "input": {
            "notifyCustomer": True,
            "lines": [
                {
                    "orderLineId": order_line_id,
                    "stocks": [{"quantity": 3, "warehouse": warehouse_id}],
                },
                {
                    "orderLineId": order_line2_id,
                    "stocks": [{"quantity": 2, "warehouse": warehouse_id}],
                },
            ],
        },
    }
    staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )

    product_variant_out_of_stock_webhooks.assert_called_once_with(Stock.objects.last())


@pytest.mark.parametrize("fulfillment_auto_approve", [True, False])
@patch("saleor.graphql.order.mutations.fulfillments.create_fulfillments")
def test_order_fulfill(
    mock_create_fulfillments,
    fulfillment_auto_approve,
    staff_api_client,
    staff_user,
    order_with_lines,
    permission_manage_orders,
    warehouse,
    site_settings,
):
    site_settings.fulfillment_auto_approve = fulfillment_auto_approve
    site_settings.save(update_fields=["fulfillment_auto_approve"])
    order = order_with_lines
    query = ORDER_FULFILL_QUERY
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line, order_line2 = order.lines.all()
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    order_line2_id = graphene.Node.to_global_id("OrderLine", order_line2.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "order": order_id,
        "input": {
            "notifyCustomer": True,
            "lines": [
                {
                    "orderLineId": order_line_id,
                    "stocks": [{"quantity": 3, "warehouse": warehouse_id}],
                },
                {
                    "orderLineId": order_line2_id,
                    "stocks": [{"quantity": 2, "warehouse": warehouse_id}],
                },
            ],
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfill"]
    assert not data["errors"]

    fulfillment_lines_for_warehouses = {
        str(warehouse.pk): [
            {"order_line": order_line, "quantity": 3},
            {"order_line": order_line2, "quantity": 2},
        ]
    }
    mock_create_fulfillments.assert_called_once_with(
        staff_user,
        None,
        order,
        fulfillment_lines_for_warehouses,
        ANY,
        True,
        approved=fulfillment_auto_approve,
    )


@patch("saleor.graphql.order.mutations.fulfillments.create_fulfillments")
def test_order_fulfill_as_app(
    mock_create_fulfillments,
    app_api_client,
    order_with_lines,
    permission_manage_orders,
    warehouse,
):
    order = order_with_lines
    query = ORDER_FULFILL_QUERY
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line, order_line2 = order.lines.all()
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    order_line2_id = graphene.Node.to_global_id("OrderLine", order_line2.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "order": order_id,
        "input": {
            "notifyCustomer": True,
            "lines": [
                {
                    "orderLineId": order_line_id,
                    "stocks": [{"quantity": 3, "warehouse": warehouse_id}],
                },
                {
                    "orderLineId": order_line2_id,
                    "stocks": [{"quantity": 2, "warehouse": warehouse_id}],
                },
            ],
        },
    }
    response = app_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfill"]
    assert not data["errors"]

    fulfillment_lines_for_warehouses = {
        str(warehouse.pk): [
            {"order_line": order_line, "quantity": 3},
            {"order_line": order_line2, "quantity": 2},
        ]
    }
    mock_create_fulfillments.assert_called_once_with(
        None,
        app_api_client.app,
        order,
        fulfillment_lines_for_warehouses,
        ANY,
        True,
        approved=True,
    )


@patch("saleor.graphql.order.mutations.fulfillments.create_fulfillments")
def test_order_fulfill_many_warehouses(
    mock_create_fulfillments,
    staff_api_client,
    staff_user,
    order_with_lines,
    permission_manage_orders,
    warehouses,
):
    order = order_with_lines
    query = ORDER_FULFILL_QUERY

    warehouse1, warehouse2 = warehouses
    order_line1, order_line2 = order.lines.all()

    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line1_id = graphene.Node.to_global_id("OrderLine", order_line1.id)
    order_line2_id = graphene.Node.to_global_id("OrderLine", order_line2.id)
    warehouse1_id = graphene.Node.to_global_id("Warehouse", warehouse1.pk)
    warehouse2_id = graphene.Node.to_global_id("Warehouse", warehouse2.pk)

    variables = {
        "order": order_id,
        "input": {
            "lines": [
                {
                    "orderLineId": order_line1_id,
                    "stocks": [{"quantity": 3, "warehouse": warehouse1_id}],
                },
                {
                    "orderLineId": order_line2_id,
                    "stocks": [
                        {"quantity": 1, "warehouse": warehouse1_id},
                        {"quantity": 1, "warehouse": warehouse2_id},
                    ],
                },
            ],
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfill"]
    assert not data["errors"]

    fulfillment_lines_for_warehouses = {
        str(warehouse1.pk): [
            {"order_line": order_line1, "quantity": 3},
            {"order_line": order_line2, "quantity": 1},
        ],
        str(warehouse2.pk): [{"order_line": order_line2, "quantity": 1}],
    }

    mock_create_fulfillments.assert_called_once_with(
        staff_user,
        None,
        order,
        fulfillment_lines_for_warehouses,
        ANY,
        True,
        approved=True,
    )


@patch("saleor.giftcard.utils.send_gift_card_notification")
@patch("saleor.graphql.order.mutations.fulfillments.create_fulfillments")
def test_order_fulfill_with_gift_cards(
    mock_create_fulfillments,
    mock_send_notification,
    staff_api_client,
    staff_user,
    order,
    gift_card_non_shippable_order_line,
    gift_card_shippable_order_line,
    permission_manage_orders,
    warehouse,
):
    query = ORDER_FULFILL_QUERY
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line, order_line2 = (
        gift_card_non_shippable_order_line,
        gift_card_shippable_order_line,
    )
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    order_line2_id = graphene.Node.to_global_id("OrderLine", order_line2.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "order": order_id,
        "input": {
            "notifyCustomer": True,
            "lines": [
                {
                    "orderLineId": order_line_id,
                    "stocks": [{"quantity": 1, "warehouse": warehouse_id}],
                },
                {
                    "orderLineId": order_line2_id,
                    "stocks": [{"quantity": 1, "warehouse": warehouse_id}],
                },
            ],
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfill"]
    assert not data["errors"]
    gift_cards = GiftCard.objects.all()
    assert gift_cards.count() == 2
    non_shippable_gift_card = gift_cards.get(
        product_id=gift_card_non_shippable_order_line.variant.product_id
    )
    shippable_gift_card = gift_cards.get(
        product_id=gift_card_shippable_order_line.variant.product_id
    )
    assert non_shippable_gift_card.initial_balance.amount == round(
        gift_card_non_shippable_order_line.total_price_gross.amount, 2
    )
    assert non_shippable_gift_card.current_balance.amount == round(
        gift_card_non_shippable_order_line.total_price_gross.amount, 2
    )
    assert shippable_gift_card.initial_balance.amount == round(
        gift_card_shippable_order_line.total_price_gross.amount, 2
    )
    assert shippable_gift_card.current_balance.amount == round(
        gift_card_shippable_order_line.total_price_gross.amount, 2
    )

    assert GiftCardEvent.objects.filter(
        gift_card=shippable_gift_card, type=GiftCardEvents.BOUGHT
    )
    assert GiftCardEvent.objects.filter(
        gift_card=non_shippable_gift_card, type=GiftCardEvents.BOUGHT
    )
    assert GiftCardEvent.objects.filter(
        gift_card=non_shippable_gift_card, type=GiftCardEvents.SENT_TO_CUSTOMER
    )

    fulfillment_lines_for_warehouses = {
        str(warehouse.pk): [
            {"order_line": order_line, "quantity": 1},
            {"order_line": order_line2, "quantity": 1},
        ]
    }
    mock_create_fulfillments.assert_called_once_with(
        staff_user,
        None,
        order,
        fulfillment_lines_for_warehouses,
        ANY,
        True,
        approved=True,
    )

    mock_send_notification.assert_called_once_with(
        staff_user, None, order.user_email, non_shippable_gift_card, ANY
    )


@patch("saleor.giftcard.utils.send_gift_card_notification")
@patch("saleor.graphql.order.mutations.fulfillments.create_fulfillments")
def test_order_fulfill_with_gift_cards_by_app(
    mock_create_fulfillments,
    mock_send_notification,
    app_api_client,
    order,
    gift_card_shippable_order_line,
    permission_manage_orders,
    warehouse,
):
    query = ORDER_FULFILL_QUERY
    app = app_api_client.app
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line = gift_card_shippable_order_line
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "order": order_id,
        "input": {
            "notifyCustomer": True,
            "lines": [
                {
                    "orderLineId": order_line_id,
                    "stocks": [{"quantity": 1, "warehouse": warehouse_id}],
                },
            ],
        },
    }
    response = app_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfill"]
    assert not data["errors"]
    shippable_gift_card = GiftCard.objects.get()
    assert shippable_gift_card.initial_balance.amount == round(
        gift_card_shippable_order_line.total_price_gross.amount, 2
    )
    assert shippable_gift_card.current_balance.amount == round(
        gift_card_shippable_order_line.total_price_gross.amount, 2
    )

    assert GiftCardEvent.objects.filter(
        gift_card=shippable_gift_card,
        type=GiftCardEvents.BOUGHT,
        user=None,
        app=app_api_client.app,
    )

    fulfillment_lines_for_warehouses = {
        str(warehouse.pk): [
            {"order_line": order_line, "quantity": 1},
        ]
    }
    mock_create_fulfillments.assert_called_once_with(
        None, app, order, fulfillment_lines_for_warehouses, ANY, True, approved=True
    )

    mock_send_notification.assert_not_called


@patch("saleor.graphql.order.mutations.fulfillments.create_fulfillments")
def test_order_fulfill_without_notification(
    mock_create_fulfillments,
    staff_api_client,
    staff_user,
    order_with_lines,
    permission_manage_orders,
    warehouse,
):
    order = order_with_lines
    query = ORDER_FULFILL_QUERY
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line = order.lines.first()
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "order": order_id,
        "input": {
            "notifyCustomer": False,
            "lines": [
                {
                    "orderLineId": order_line_id,
                    "stocks": [{"quantity": 1, "warehouse": warehouse_id}],
                }
            ],
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfill"]
    assert not data["errors"]

    fulfillment_lines_for_warehouses = {
        str(warehouse.pk): [{"order_line": order_line, "quantity": 1}]
    }
    mock_create_fulfillments.assert_called_once_with(
        staff_user,
        None,
        order,
        fulfillment_lines_for_warehouses,
        ANY,
        False,
        approved=True,
    )


@patch("saleor.graphql.order.mutations.fulfillments.create_fulfillments")
def test_order_fulfill_lines_with_empty_quantity(
    mock_create_fulfillments,
    staff_api_client,
    staff_user,
    order_with_lines,
    permission_manage_orders,
    warehouse,
    warehouse_no_shipping_zone,
):
    order = order_with_lines
    query = ORDER_FULFILL_QUERY
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line, order_line2 = order.lines.all()
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    order_line2_id = graphene.Node.to_global_id("OrderLine", order_line2.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    warehouse2_id = graphene.Node.to_global_id(
        "Warehouse", warehouse_no_shipping_zone.pk
    )
    assert not order.events.all()
    variables = {
        "order": order_id,
        "input": {
            "lines": [
                {
                    "orderLineId": order_line_id,
                    "stocks": [
                        {"quantity": 0, "warehouse": warehouse_id},
                        {"quantity": 0, "warehouse": warehouse2_id},
                    ],
                },
                {
                    "orderLineId": order_line2_id,
                    "stocks": [
                        {"quantity": 2, "warehouse": warehouse_id},
                        {"quantity": 0, "warehouse": warehouse2_id},
                    ],
                },
            ],
        },
    }
    variables["input"]["lines"][0]["stocks"][0]["quantity"] = 0
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfill"]
    assert not data["errors"]

    fulfillment_lines_for_warehouses = {
        str(warehouse.pk): [{"order_line": order_line2, "quantity": 2}]
    }
    mock_create_fulfillments.assert_called_once_with(
        staff_user,
        None,
        order,
        fulfillment_lines_for_warehouses,
        ANY,
        True,
        approved=True,
    )


@patch("saleor.graphql.order.mutations.fulfillments.create_fulfillments")
def test_order_fulfill_zero_quantity(
    mock_create_fulfillments,
    staff_api_client,
    staff_user,
    order_with_lines,
    permission_manage_orders,
    warehouse,
):
    query = ORDER_FULFILL_QUERY
    order_id = graphene.Node.to_global_id("Order", order_with_lines.id)
    order_line = order_with_lines.lines.first()
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "order": order_id,
        "input": {
            "lines": [
                {
                    "orderLineId": order_line_id,
                    "stocks": [{"quantity": 0, "warehouse": warehouse_id}],
                }
            ]
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfill"]
    assert data["errors"]
    error = data["errors"][0]
    assert error["field"] == "lines"
    assert error["code"] == OrderErrorCode.ZERO_QUANTITY.name
    assert not error["orderLines"]
    assert not error["warehouse"]

    mock_create_fulfillments.assert_not_called()


def test_order_fulfill_channel_without_shipping_zones(
    staff_api_client,
    order_with_lines,
    permission_manage_orders,
    warehouse,
):
    order = order_with_lines
    order.channel.shipping_zones.clear()
    query = ORDER_FULFILL_QUERY
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line = order.lines.first()
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "order": order_id,
        "input": {
            "notifyCustomer": True,
            "lines": [
                {
                    "orderLineId": order_line_id,
                    "stocks": [{"quantity": 3, "warehouse": warehouse_id}],
                },
            ],
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfill"]
    assert len(data["errors"]) == 1
    error = data["errors"][0]
    assert error["field"] == "stocks"
    assert error["code"] == OrderErrorCode.INSUFFICIENT_STOCK.name


@patch("saleor.graphql.order.mutations.fulfillments.create_fulfillments")
def test_order_fulfill_fulfilled_order(
    mock_create_fulfillments,
    staff_api_client,
    staff_user,
    order_with_lines,
    permission_manage_orders,
    warehouse,
):
    query = ORDER_FULFILL_QUERY
    order_id = graphene.Node.to_global_id("Order", order_with_lines.id)
    order_line = order_with_lines.lines.first()
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "order": order_id,
        "input": {
            "lines": [
                {
                    "orderLineId": order_line_id,
                    "stocks": [{"quantity": 100, "warehouse": warehouse_id}],
                }
            ]
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfill"]
    assert data["errors"]
    error = data["errors"][0]
    assert error["field"] == "orderLineId"
    assert error["code"] == OrderErrorCode.FULFILL_ORDER_LINE.name
    assert error["orderLines"] == [order_line_id]
    assert not error["warehouse"]

    mock_create_fulfillments.assert_not_called()


@patch("saleor.graphql.order.mutations.fulfillments.create_fulfillments")
def test_order_fulfill_unpaid_order_and_disallow_unpaid(
    mock_create_fulfillments,
    staff_api_client,
    order_with_lines,
    permission_manage_orders,
    warehouse,
    site_settings,
):
    site_settings.fulfillment_allow_unpaid = False
    site_settings.save(update_fields=["fulfillment_allow_unpaid"])
    query = ORDER_FULFILL_QUERY
    order_id = graphene.Node.to_global_id("Order", order_with_lines.id)
    order_line = order_with_lines.lines.first()
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "order": order_id,
        "input": {
            "lines": [
                {
                    "orderLineId": order_line_id,
                    "stocks": [{"quantity": 100, "warehouse": warehouse_id}],
                }
            ]
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfill"]
    assert data["errors"]
    error = data["errors"][0]
    assert error["field"] == "order"
    assert error["code"] == OrderErrorCode.CANNOT_FULFILL_UNPAID_ORDER.name

    mock_create_fulfillments.assert_not_called()


@patch("saleor.graphql.order.mutations.fulfillments.create_fulfillments", autospec=True)
def test_order_fulfill_warehouse_with_insufficient_stock_exception(
    mock_create_fulfillments,
    staff_api_client,
    order_with_lines,
    permission_manage_orders,
    warehouse_no_shipping_zone,
):
    order = order_with_lines
    query = ORDER_FULFILL_QUERY
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line = order.lines.first()
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    warehouse_id = graphene.Node.to_global_id(
        "Warehouse", warehouse_no_shipping_zone.pk
    )
    variables = {
        "order": order_id,
        "input": {
            "lines": [
                {
                    "orderLineId": order_line_id,
                    "stocks": [{"quantity": 1, "warehouse": warehouse_id}],
                }
            ]
        },
    }

    mock_create_fulfillments.side_effect = InsufficientStock(
        [
            InsufficientStockData(
                variant=order_line.variant,
                order_line=order_line,
                warehouse_pk=warehouse_no_shipping_zone.pk,
            )
        ]
    )

    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfill"]
    assert data["errors"]
    error = data["errors"][0]
    assert error["field"] == "stocks"
    assert error["code"] == OrderErrorCode.INSUFFICIENT_STOCK.name
    assert error["orderLines"] == [order_line_id]
    assert error["warehouse"] == warehouse_id


@patch("saleor.graphql.order.mutations.fulfillments.create_fulfillments", autospec=True)
def test_order_fulfill_warehouse_duplicated_warehouse_id(
    mock_create_fulfillments,
    staff_api_client,
    order_with_lines,
    permission_manage_orders,
    warehouse,
):
    order = order_with_lines
    query = ORDER_FULFILL_QUERY
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line = order.lines.first()
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "order": order_id,
        "input": {
            "lines": [
                {
                    "orderLineId": order_line_id,
                    "stocks": [
                        {"quantity": 1, "warehouse": warehouse_id},
                        {"quantity": 2, "warehouse": warehouse_id},
                    ],
                }
            ]
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfill"]
    assert data["errors"]
    error = data["errors"][0]
    assert error["field"] == "warehouse"
    assert error["code"] == OrderErrorCode.DUPLICATED_INPUT_ITEM.name
    assert not error["orderLines"]
    assert error["warehouse"] == warehouse_id
    mock_create_fulfillments.assert_not_called()


@patch("saleor.graphql.order.mutations.fulfillments.create_fulfillments", autospec=True)
def test_order_fulfill_warehouse_duplicated_order_line_id(
    mock_create_fulfillments,
    staff_api_client,
    order_with_lines,
    permission_manage_orders,
    warehouse,
):
    order = order_with_lines
    query = ORDER_FULFILL_QUERY
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line = order.lines.first()
    order_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "order": order_id,
        "input": {
            "lines": [
                {
                    "orderLineId": order_line_id,
                    "stocks": [{"quantity": 3, "warehouse": warehouse_id}],
                },
                {
                    "orderLineId": order_line_id,
                    "stocks": [{"quantity": 3, "warehouse": warehouse_id}],
                },
            ]
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfill"]
    assert data["errors"]
    error = data["errors"][0]
    assert error["field"] == "orderLineId"
    assert error["code"] == OrderErrorCode.DUPLICATED_INPUT_ITEM.name
    assert error["orderLines"] == [order_line_id]
    assert not error["warehouse"]
    mock_create_fulfillments.assert_not_called()


@patch("saleor.plugins.manager.PluginsManager.notify")
def test_fulfillment_update_tracking(
    send_fulfillment_update_mock,
    staff_api_client,
    fulfillment,
    permission_manage_orders,
):
    query = """
        mutation updateFulfillment($id: ID!, $tracking: String) {
            orderFulfillmentUpdateTracking(
                id: $id, input: { trackingNumber: $tracking }
            ) {
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
    mutation updateFulfillment(
        $id: ID!
        $tracking: String
        $notifyCustomer: Boolean
    ) {
        orderFulfillmentUpdateTracking(
            id: $id
            input: { trackingNumber: $tracking, notifyCustomer: $notifyCustomer }
        ) {
            fulfillment {
                trackingNumber
            }
        }
    }
"""


@patch("saleor.graphql.order.mutations.fulfillments.send_fulfillment_update")
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
        fulfillment.order, fulfillment, ANY
    )


@patch("saleor.order.notifications.send_fulfillment_update")
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


CANCEL_FULFILLMENT_MUTATION = """
    mutation cancelFulfillment($id: ID!, $warehouseId: ID) {
        orderFulfillmentCancel(id: $id, input: {warehouseId: $warehouseId}) {
            fulfillment {
                status
            }
            order {
                status
            }
            errors {
                code
                field
            }
        }
    }
"""


def test_cancel_fulfillment(
    staff_api_client, fulfillment, staff_user, permission_manage_orders, warehouse
):
    query = CANCEL_FULFILLMENT_MUTATION
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.id)
    variables = {"id": fulfillment_id, "warehouseId": warehouse_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentCancel"]
    assert data["fulfillment"]["status"] == FulfillmentStatus.CANCELED.upper()
    assert data["order"]["status"] == OrderStatus.UNFULFILLED.upper()
    event_cancelled, event_restocked_items = fulfillment.order.events.all()
    assert event_cancelled.type == (OrderEvents.FULFILLMENT_CANCELED)
    assert event_cancelled.parameters == {"composed_id": fulfillment.composed_id}
    assert event_cancelled.user == staff_user

    assert event_restocked_items.type == (OrderEvents.FULFILLMENT_RESTOCKED_ITEMS)
    assert event_restocked_items.parameters == {
        "quantity": fulfillment.get_total_quantity(),
        "warehouse": str(warehouse.pk),
    }
    assert event_restocked_items.user == staff_user
    assert Fulfillment.objects.filter(
        pk=fulfillment.pk, status=FulfillmentStatus.CANCELED
    ).exists()


def test_cancel_fulfillment_no_warehouse_id(
    staff_api_client, fulfillment, permission_manage_orders
):
    query = """
        mutation cancelFulfillment($id: ID!) {
            orderFulfillmentCancel(id: $id) {
                fulfillment {
                    status
                }
                order {
                    status
                }
                errors {
                    code
                    field
                }
            }
        }
    """
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    variables = {"id": fulfillment_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    errors = content["data"]["orderFulfillmentCancel"]["errors"]
    assert len(errors) == 1
    error = errors[0]
    assert error["field"] == "warehouseId"
    assert error["code"] == OrderErrorCode.REQUIRED.name


@patch("saleor.order.actions.restock_fulfillment_lines")
def test_cancel_fulfillment_awaiting_approval(
    mock_restock_lines, staff_api_client, fulfillment, permission_manage_orders
):
    fulfillment.status = FulfillmentStatus.WAITING_FOR_APPROVAL
    fulfillment.save(update_fields=["status"])
    query = CANCEL_FULFILLMENT_MUTATION
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    variables = {"id": fulfillment_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentCancel"]
    assert data["fulfillment"] is None
    mock_restock_lines.assert_not_called()
    event_cancelled = fulfillment.order.events.get()
    assert event_cancelled.type == (OrderEvents.FULFILLMENT_CANCELED)
    assert event_cancelled.parameters == {}
    assert event_cancelled.user == staff_api_client.user
    assert not Fulfillment.objects.filter(pk=fulfillment.pk).exists()


@patch("saleor.order.actions.restock_fulfillment_lines")
def test_cancel_fulfillment_awaiting_approval_warehouse_specified(
    mock_restock_lines,
    staff_api_client,
    fulfillment,
    permission_manage_orders,
    warehouse,
):
    fulfillment.status = FulfillmentStatus.WAITING_FOR_APPROVAL
    fulfillment.save(update_fields=["status"])
    query = CANCEL_FULFILLMENT_MUTATION
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.id)
    variables = {"id": fulfillment_id, "warehouseId": warehouse_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentCancel"]
    assert data["fulfillment"] is None
    mock_restock_lines.assert_not_called()
    event_cancelled = fulfillment.order.events.get()
    assert event_cancelled.type == (OrderEvents.FULFILLMENT_CANCELED)
    assert event_cancelled.parameters == {}
    assert event_cancelled.user == staff_api_client.user
    assert not Fulfillment.objects.filter(pk=fulfillment.pk).exists()


def test_cancel_fulfillment_canceled_state(
    staff_api_client, fulfillment, permission_manage_orders, warehouse
):
    query = CANCEL_FULFILLMENT_MUTATION
    fulfillment.status = FulfillmentStatus.CANCELED
    fulfillment.save(update_fields=["status"])
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.id)
    variables = {"id": fulfillment_id, "warehouseId": warehouse_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    errors = content["data"]["orderFulfillmentCancel"]["errors"]
    assert len(errors) == 1
    error = errors[0]
    assert error["field"] == "fulfillment"
    assert error["code"] == OrderErrorCode.CANNOT_CANCEL_FULFILLMENT.name


def test_cancel_fulfillment_warehouse_without_stock(
    order_line, warehouse, staff_api_client, permission_manage_orders, staff_user
):
    query = CANCEL_FULFILLMENT_MUTATION
    order = order_line.order
    fulfillment = order.fulfillments.create(tracking_number="123")
    fulfillment.lines.create(order_line=order_line, quantity=order_line.quantity)
    order.status = OrderStatus.FULFILLED
    order.save(update_fields=["status"])

    assert not Stock.objects.filter(
        warehouse=warehouse, product_variant=order_line.variant
    )
    assert not Allocation.objects.filter(order_line=order_line)

    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.id)
    variables = {"id": fulfillment_id, "warehouseId": warehouse_id}
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
        "quantity": fulfillment.get_total_quantity(),
        "warehouse": str(warehouse.pk),
    }
    assert event_restocked_items.user == staff_user

    stock = Stock.objects.filter(
        warehouse=warehouse, product_variant=order_line.variant
    ).first()
    assert stock.quantity == order_line.quantity
    allocation = order_line.allocations.filter(stock=stock).first()
    assert allocation.quantity_allocated == order_line.quantity


@patch("saleor.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_digital_fulfillment(
    mock_email_fulfillment,
    digital_content,
    staff_api_client,
    order_with_lines,
    warehouse,
    permission_manage_orders,
):
    order = order_with_lines
    query = ORDER_FULFILL_QUERY
    order_id = graphene.Node.to_global_id("Order", order.id)
    order_line = order.lines.first()
    order_line.variant = digital_content.product_variant
    order_line.save()
    order_line.allocations.all().delete()

    stock = digital_content.product_variant.stocks.get(warehouse=warehouse)
    Allocation.objects.create(
        order_line=order_line, stock=stock, quantity_allocated=order_line.quantity
    )

    second_line = order.lines.last()
    first_line_id = graphene.Node.to_global_id("OrderLine", order_line.id)
    second_line_id = graphene.Node.to_global_id("OrderLine", second_line.id)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)

    variables = {
        "order": order_id,
        "input": {
            "notifyCustomer": True,
            "lines": [
                {
                    "orderLineId": first_line_id,
                    "stocks": [{"quantity": 1, "warehouse": warehouse_id}],
                },
                {
                    "orderLineId": second_line_id,
                    "stocks": [{"quantity": 1, "warehouse": warehouse_id}],
                },
            ],
        },
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    get_graphql_content(response)

    assert mock_email_fulfillment.call_count == 1


APPROVE_FULFILLMENT_MUTATION = """
    mutation approveFulfillment($id: ID!, $notifyCustomer: Boolean!) {
        orderFulfillmentApprove(id: $id, notifyCustomer: $notifyCustomer) {
            fulfillment {
                status
            }
            order {
                status
            }
            errors {
                field
                code
            }
        }
    }
"""


@patch("saleor.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_fulfillment_approve(
    mock_email_fulfillment,
    staff_api_client,
    fulfillment,
    permission_manage_orders,
):
    fulfillment.status = FulfillmentStatus.WAITING_FOR_APPROVAL
    fulfillment.save(update_fields=["status"])
    query = APPROVE_FULFILLMENT_MUTATION
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    variables = {"id": fulfillment_id, "notifyCustomer": True}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentApprove"]
    assert not data["errors"]
    assert data["fulfillment"]["status"] == FulfillmentStatus.FULFILLED.upper()
    assert data["order"]["status"] == OrderStatus.FULFILLED.upper()
    fulfillment.refresh_from_db()
    assert fulfillment.status == FulfillmentStatus.FULFILLED

    assert mock_email_fulfillment.call_count == 1
    events = fulfillment.order.events.all()
    assert len(events) == 1
    event = events[0]
    assert event.type == OrderEvents.FULFILLMENT_FULFILLED_ITEMS
    assert event.user == staff_api_client.user


@patch("saleor.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_fulfillment_approve_partial_order_fulfill(
    mock_email_fulfillment,
    staff_api_client,
    fulfillment_awaiting_approval,
    permission_manage_orders,
):
    query = APPROVE_FULFILLMENT_MUTATION
    second_fulfillment = Fulfillment.objects.get(pk=fulfillment_awaiting_approval.pk)
    second_fulfillment.pk = None
    second_fulfillment.save()
    fulfillment_id = graphene.Node.to_global_id(
        "Fulfillment", fulfillment_awaiting_approval.id
    )
    variables = {"id": fulfillment_id, "notifyCustomer": False}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentApprove"]
    assert not data["errors"]
    assert data["fulfillment"]["status"] == FulfillmentStatus.FULFILLED.upper()
    assert data["order"]["status"] == "PARTIALLY_FULFILLED"
    fulfillment_awaiting_approval.refresh_from_db()
    assert fulfillment_awaiting_approval.status == FulfillmentStatus.FULFILLED

    assert mock_email_fulfillment.call_count == 0


def test_fulfillment_approve_invalid_status(
    staff_api_client,
    fulfillment,
    permission_manage_orders,
):
    query = APPROVE_FULFILLMENT_MUTATION
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    variables = {"id": fulfillment_id, "notifyCustomer": True}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentApprove"]
    assert data["errors"][0]["code"] == OrderErrorCode.INVALID.name


def test_fulfillment_approve_order_unpaid(
    staff_api_client,
    fulfillment,
    site_settings,
    permission_manage_orders,
):
    site_settings.fulfillment_allow_unpaid = False
    site_settings.save(update_fields=["fulfillment_allow_unpaid"])
    fulfillment.status = FulfillmentStatus.WAITING_FOR_APPROVAL
    fulfillment.save(update_fields=["status"])
    query = APPROVE_FULFILLMENT_MUTATION
    fulfillment_id = graphene.Node.to_global_id("Fulfillment", fulfillment.id)
    variables = {"id": fulfillment_id, "notifyCustomer": True}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["orderFulfillmentApprove"]
    assert data["errors"][0]["code"] == OrderErrorCode.CANNOT_FULFILL_UNPAID_ORDER.name


QUERY_FULFILLMENT = """
    query fulfillment($id: ID!) {
        order(id: $id) {
            fulfillments {
                id
                fulfillmentOrder
                status
                trackingNumber
                warehouse {
                    id
                }
                lines {
                    orderLine {
                        id
                    }
                    quantity
                }
            }
        }
    }
"""


def test_fulfillment_query(
    staff_api_client,
    fulfilled_order,
    warehouse,
    permission_manage_orders,
):
    order = fulfilled_order
    order_line_1, order_line_2 = order.lines.all()
    order_id = graphene.Node.to_global_id("Order", order.pk)
    order_line_1_id = graphene.Node.to_global_id("OrderLine", order_line_1.pk)
    order_line_2_id = graphene.Node.to_global_id("OrderLine", order_line_2.pk)
    warehose_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {"id": order_id}
    response = staff_api_client.post_graphql(
        QUERY_FULFILLMENT, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["order"]["fulfillments"]
    assert len(data) == 1
    fulfillment_data = data[0]

    assert fulfillment_data["fulfillmentOrder"] == 1
    assert fulfillment_data["status"] == FulfillmentStatus.FULFILLED.upper()
    assert fulfillment_data["trackingNumber"] == "123"
    assert fulfillment_data["warehouse"]["id"] == warehose_id
    assert len(fulfillment_data["lines"]) == 2
    assert {
        "orderLine": {"id": order_line_1_id},
        "quantity": order_line_1.quantity,
    } in fulfillment_data["lines"]
    assert {
        "orderLine": {"id": order_line_2_id},
        "quantity": order_line_2.quantity,
    } in fulfillment_data["lines"]


QUERY_ORDER_FULFILL_DATA = """
    query OrderFulfillData($id: ID!) {
        order(id: $id) {
            id
            lines {
                variant {
                    stocks {
                        warehouse {
                            id
                        }
                        quantity
                        quantityAllocated
                    }
                }
            }
        }
    }
"""


def test_staff_can_query_order_fulfill_data(
    staff_api_client, order_with_lines, permission_manage_orders
):
    order_id = graphene.Node.to_global_id("Order", order_with_lines.pk)
    variables = {"id": order_id}
    response = staff_api_client.post_graphql(
        QUERY_ORDER_FULFILL_DATA, variables, permissions=[permission_manage_orders]
    )
    content = get_graphql_content(response)
    data = content["data"]["order"]["lines"]
    assert len(data) == 2
    assert data[0]["variant"]["stocks"][0]["quantity"] == 5
    assert data[0]["variant"]["stocks"][0]["quantityAllocated"] == 3
    assert data[1]["variant"]["stocks"][0]["quantity"] == 2
    assert data[1]["variant"]["stocks"][0]["quantityAllocated"] == 2


def test_staff_can_query_order_fulfill_data_without_permission(
    staff_api_client, order_with_lines
):
    order_id = graphene.Node.to_global_id("Order", order_with_lines.pk)
    variables = {"id": order_id}
    response = staff_api_client.post_graphql(QUERY_ORDER_FULFILL_DATA, variables)
    assert_no_permission(response)
