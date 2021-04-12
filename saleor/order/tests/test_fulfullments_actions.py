from unittest.mock import patch

import pytest

from ...core.exceptions import InsufficientStock
from ...plugins.manager import get_plugins_manager
from ...tests.utils import flush_post_commit_hooks
from ...warehouse.models import Allocation, Stock
from ..actions import create_fulfillments
from ..models import FulfillmentLine, OrderStatus


@patch("saleor.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments(
    mock_email_fulfillment,
    staff_user,
    order_with_lines,
    warehouse,
):
    order = order_with_lines
    order_line1, order_line2 = order.lines.all()
    fulfillment_lines_for_warehouses = {
        str(warehouse.pk): [
            {"order_line": order_line1, "quantity": 3},
            {"order_line": order_line2, "quantity": 2},
        ]
    }
    manager = get_plugins_manager()
    [fulfillment] = create_fulfillments(
        staff_user, order, fulfillment_lines_for_warehouses, manager, True
    )
    flush_post_commit_hooks()

    order.refresh_from_db()
    fulfillment_lines = FulfillmentLine.objects.filter(
        fulfillment__order=order
    ).order_by("pk")
    assert fulfillment_lines[0].stock == order_line1.variant.stocks.get()
    assert fulfillment_lines[0].quantity == 3
    assert fulfillment_lines[1].stock == order_line2.variant.stocks.get()
    assert fulfillment_lines[1].quantity == 2

    assert order.status == OrderStatus.FULFILLED
    assert order.fulfillments.get() == fulfillment

    order_line1, order_line2 = order.lines.all()
    assert order_line1.quantity_fulfilled == 3
    assert order_line2.quantity_fulfilled == 2

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 0
    )

    mock_email_fulfillment.assert_called_once_with(
        order, order.fulfillments.get(), staff_user, manager
    )


@patch("saleor.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments_without_notification(
    mock_email_fulfillment,
    staff_user,
    order_with_lines,
    warehouse,
):
    order = order_with_lines
    order_line1, order_line2 = order.lines.all()
    fulfillment_lines_for_warehouses = {
        str(warehouse.pk): [
            {"order_line": order_line1, "quantity": 3},
            {"order_line": order_line2, "quantity": 2},
        ]
    }

    [fulfillment] = create_fulfillments(
        staff_user,
        order,
        fulfillment_lines_for_warehouses,
        get_plugins_manager(),
        False,
    )
    flush_post_commit_hooks()

    order.refresh_from_db()
    fulfillment_lines = FulfillmentLine.objects.filter(
        fulfillment__order=order
    ).order_by("pk")
    assert fulfillment_lines[0].stock == order_line1.variant.stocks.get()
    assert fulfillment_lines[0].quantity == 3
    assert fulfillment_lines[1].stock == order_line2.variant.stocks.get()
    assert fulfillment_lines[1].quantity == 2

    assert order.status == OrderStatus.FULFILLED
    assert order.fulfillments.get() == fulfillment

    order_line1, order_line2 = order.lines.all()
    assert order_line1.quantity_fulfilled == 3
    assert order_line2.quantity_fulfilled == 2

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 0
    )

    mock_email_fulfillment.assert_not_called()


def test_create_fulfillments_many_warehouses(
    staff_user,
    order_with_lines,
    warehouses_with_shipping_zone,
):
    order = order_with_lines
    warehouse1, warehouse2 = warehouses_with_shipping_zone
    order_line1, order_line2 = order.lines.all()

    stock_w1_l1 = Stock(
        warehouse=warehouse1, product_variant=order_line1.variant, quantity=3
    )
    stock_w1_l2 = Stock(
        warehouse=warehouse1, product_variant=order_line2.variant, quantity=1
    )
    stock_w2_l2 = Stock(
        warehouse=warehouse2, product_variant=order_line2.variant, quantity=1
    )
    Stock.objects.bulk_create([stock_w1_l1, stock_w1_l2, stock_w2_l2])
    fulfillment_lines_for_warehouses = {
        str(warehouse1.pk): [
            {"order_line": order_line1, "quantity": 3},
            {"order_line": order_line2, "quantity": 1},
        ],
        str(warehouse2.pk): [{"order_line": order_line2, "quantity": 1}],
    }

    [fulfillment1, fulfillment2] = create_fulfillments(
        staff_user,
        order,
        fulfillment_lines_for_warehouses,
        get_plugins_manager(),
        False,
    )
    flush_post_commit_hooks()

    order.refresh_from_db()
    fulfillment_lines = FulfillmentLine.objects.filter(
        fulfillment__order=order
    ).order_by("pk")
    assert fulfillment_lines[0].stock == stock_w1_l1
    assert fulfillment_lines[0].quantity == 3
    assert fulfillment_lines[1].stock == stock_w1_l2
    assert fulfillment_lines[1].quantity == 1
    assert fulfillment_lines[2].stock == stock_w2_l2
    assert fulfillment_lines[2].quantity == 1

    assert order.status == OrderStatus.FULFILLED
    assert order.fulfillments.get(fulfillment_order=1) == fulfillment1
    assert order.fulfillments.get(fulfillment_order=2) == fulfillment2

    order_line1, order_line2 = order.lines.all()
    assert order_line1.quantity_fulfilled == 3
    assert order_line2.quantity_fulfilled == 2

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 0
    )


@patch("saleor.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments_with_one_line_empty_quantity(
    mock_email_fulfillment,
    staff_user,
    order_with_lines,
    warehouse,
):
    order = order_with_lines
    order_line1, order_line2 = order.lines.all()
    fulfillment_lines_for_warehouses = {
        str(warehouse.pk): [
            {"order_line": order_line1, "quantity": 0},
            {"order_line": order_line2, "quantity": 2},
        ]
    }

    manager = get_plugins_manager()
    [fulfillment] = create_fulfillments(
        staff_user, order, fulfillment_lines_for_warehouses, manager, True
    )
    flush_post_commit_hooks()

    order.refresh_from_db()
    fulfillment_lines = FulfillmentLine.objects.filter(
        fulfillment__order=order
    ).order_by("pk")
    assert fulfillment_lines[0].stock == order_line2.variant.stocks.get()
    assert fulfillment_lines[0].quantity == 2

    assert order.status == OrderStatus.PARTIALLY_FULFILLED
    assert order.fulfillments.get() == fulfillment

    order_line1, order_line2 = order.lines.all()
    assert order_line1.quantity_fulfilled == 0
    assert order_line2.quantity_fulfilled == 2

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 1
    )

    mock_email_fulfillment.assert_called_once_with(
        order, order.fulfillments.get(), staff_user, manager
    )


@patch("saleor.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments_with_variant_without_inventory_tracking(
    mock_email_fulfillment,
    staff_user,
    order_with_line_without_inventory_tracking,
    warehouse,
):
    order = order_with_line_without_inventory_tracking
    order_line = order.lines.get()
    stock = order_line.variant.stocks.get()
    stock_quantity_before = stock.quantity
    fulfillment_lines_for_warehouses = {
        str(warehouse.pk): [{"order_line": order_line, "quantity": 2}]
    }

    manager = get_plugins_manager()
    [fulfillment] = create_fulfillments(
        staff_user, order, fulfillment_lines_for_warehouses, manager, True
    )
    flush_post_commit_hooks()

    order.refresh_from_db()
    fulfillment_lines = FulfillmentLine.objects.filter(
        fulfillment__order=order
    ).order_by("pk")
    assert fulfillment_lines[0].stock == order_line.variant.stocks.get()
    assert fulfillment_lines[0].quantity == 2

    assert order.status == OrderStatus.PARTIALLY_FULFILLED
    assert order.fulfillments.get() == fulfillment

    order_line = order.lines.get()
    assert order_line.quantity_fulfilled == 2

    stock.refresh_from_db()
    assert stock_quantity_before == stock.quantity

    mock_email_fulfillment.assert_called_once_with(
        order, order.fulfillments.get(), staff_user, manager
    )


@patch("saleor.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments_without_allocations(
    mock_email_fulfillment,
    staff_user,
    order_with_lines,
    warehouse,
):

    order = order_with_lines
    order_line1, order_line2 = order.lines.all()
    Allocation.objects.filter(order_line__order=order).delete()
    fulfillment_lines_for_warehouses = {
        str(warehouse.pk): [
            {"order_line": order_line1, "quantity": 3},
            {"order_line": order_line2, "quantity": 2},
        ]
    }

    manager = get_plugins_manager()
    [fulfillment] = create_fulfillments(
        staff_user, order, fulfillment_lines_for_warehouses, manager, True
    )
    flush_post_commit_hooks()

    order.refresh_from_db()
    fulfillment_lines = FulfillmentLine.objects.filter(
        fulfillment__order=order
    ).order_by("pk")
    assert fulfillment_lines[0].stock == order_line1.variant.stocks.get()
    assert fulfillment_lines[0].quantity == 3
    assert fulfillment_lines[1].stock == order_line2.variant.stocks.get()
    assert fulfillment_lines[1].quantity == 2

    assert order.status == OrderStatus.FULFILLED
    assert order.fulfillments.get() == fulfillment

    order_line1, order_line2 = order.lines.all()
    assert order_line1.quantity_fulfilled == 3
    assert order_line2.quantity_fulfilled == 2

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 0
    )

    mock_email_fulfillment.assert_called_once_with(
        order, order.fulfillments.get(), staff_user, manager
    )


@patch("saleor.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments_warehouse_without_stock(
    mock_email_fulfillment,
    staff_user,
    order_with_lines,
    warehouse_no_shipping_zone,
):
    order = order_with_lines
    order_line1, order_line2 = order.lines.all()
    fulfillment_lines_for_warehouses = {
        str(warehouse_no_shipping_zone.pk): [
            {"order_line": order_line1, "quantity": 3},
            {"order_line": order_line2, "quantity": 2},
        ]
    }

    with pytest.raises(InsufficientStock) as exc:
        create_fulfillments(
            staff_user,
            order,
            fulfillment_lines_for_warehouses,
            get_plugins_manager(),
            True,
        )

    assert len(exc.value.items) == 2
    assert {item.variant for item in exc.value.items} == {
        order_line1.variant,
        order_line2.variant,
    }
    assert {item.order_line for item in exc.value.items} == {order_line1, order_line2}
    assert {item.warehouse_pk for item in exc.value.items} == {
        str(warehouse_no_shipping_zone.pk)
    }

    order.refresh_from_db()
    assert FulfillmentLine.objects.filter(fulfillment__order=order).count() == 0

    assert order.status == OrderStatus.UNFULFILLED
    assert order.fulfillments.all().count() == 0

    order_line1, order_line2 = order.lines.all()
    assert order_line1.quantity_fulfilled == 0
    assert order_line2.quantity_fulfilled == 0

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 2
    )

    mock_email_fulfillment.assert_not_called()


@patch("saleor.order.actions.send_fulfillment_confirmation_to_customer", autospec=True)
def test_create_fulfillments_with_variant_without_inventory_tracking_and_without_stock(
    mock_email_fulfillment,
    staff_user,
    order_with_line_without_inventory_tracking,
    warehouse_no_shipping_zone,
):
    order = order_with_line_without_inventory_tracking
    order_line = order.lines.get()
    fulfillment_lines_for_warehouses = {
        str(warehouse_no_shipping_zone.pk): [{"order_line": order_line, "quantity": 2}]
    }

    with pytest.raises(InsufficientStock) as exc:
        create_fulfillments(
            staff_user,
            order,
            fulfillment_lines_for_warehouses,
            get_plugins_manager(),
            True,
        )

    assert len(exc.value.items) == 1
    assert exc.value.items[0].variant == order_line.variant
    assert exc.value.items[0].order_line == order_line
    assert exc.value.items[0].warehouse_pk == str(warehouse_no_shipping_zone.pk)

    order.refresh_from_db()
    assert FulfillmentLine.objects.filter(fulfillment__order=order).count() == 0

    assert order.status == OrderStatus.UNFULFILLED
    assert order.fulfillments.all().count() == 0

    order_line = order.lines.get()
    assert order_line.quantity_fulfilled == 0

    assert (
        Allocation.objects.filter(
            order_line__order=order, quantity_allocated__gt=0
        ).count()
        == 0
    )

    mock_email_fulfillment.assert_not_called()
