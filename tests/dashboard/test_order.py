from decimal import Decimal

from django.urls import reverse
import pytest
from tests.utils import get_redirect_location, get_url_path

from saleor.dashboard.order.forms import ChangeQuantityForm, MoveLinesForm
from saleor.order import OrderStatus
from saleor.order.models import (
    DeliveryGroup, Order, OrderHistoryEntry, OrderLine)
from saleor.order.utils import (
    add_variant_to_existing_lines, change_order_line_quantity,
    fill_group_with_partition, remove_empty_groups)
from saleor.product.models import ProductVariant, Stock, StockLocation


@pytest.mark.integration
@pytest.mark.django_db
def test_view_cancel_order_line(admin_client, order_with_lines_and_stock):
    lines_before = order_with_lines_and_stock.get_lines()
    lines_before_count = lines_before.count()
    line = lines_before.first()
    line_quantity = line.quantity
    quantity_allocated_before = line.stock.quantity_allocated
    product = line.product

    url = reverse(
        'dashboard:orderline-cancel', kwargs={
            'order_pk': order_with_lines_and_stock.pk,
            'line_pk': line.pk})

    response = admin_client.get(url)
    assert response.status_code == 200
    response = admin_client.post(url, {'csrfmiddlewaretoken': 'hello'})
    assert response.status_code == 302
    assert get_redirect_location(response) == reverse(
        'dashboard:order-details', args=[order_with_lines_and_stock.pk])
    # check ordered item removal
    lines_after = Order.objects.get().get_lines()
    assert lines_before_count - 1 == lines_after.count()
    # check stock deallocation
    assert Stock.objects.first().quantity_allocated == quantity_allocated_before - line_quantity
    # check note in the order's history
    assert OrderHistoryEntry.objects.get(
        order=order_with_lines_and_stock).comment == 'Cancelled item %s' % product
    url = reverse(
        'dashboard:orderline-cancel', kwargs={
            'order_pk': order_with_lines_and_stock.pk,
            'line_pk': OrderLine.objects.get().pk})
    response = admin_client.post(
        url, {'csrfmiddlewaretoken': 'hello'}, follow=True)
    # check shipment group removal if it becomes empty
    assert Order.objects.get().get_lines().count() == 0
    assert DeliveryGroup.objects.count() == 0
    # check success messages after redirect
    assert response.context['messages']


@pytest.mark.integration
@pytest.mark.django_db
def test_view_change_order_line_quantity(admin_client, order_with_lines_and_stock):
    """
    user goes to order details page
    user selects first order line with quantity 3 and changes it to 2
    """
    lines_before_quantity_change = order_with_lines_and_stock.get_lines()
    lines_before_quantity_change_count = lines_before_quantity_change.count()
    line = lines_before_quantity_change.first()
    line_quantity_before_quantity_change = line.quantity

    url = reverse(
        'dashboard:orderline-change-quantity', kwargs={
            'order_pk': order_with_lines_and_stock.pk,
            'line_pk': line.pk})
    response = admin_client.get(url)
    assert response.status_code == 200
    response = admin_client.post(
        url, {'quantity': 2}, follow=True)
    redirected_to, redirect_status_code = response.redirect_chain[-1]
    # check redirection
    assert redirect_status_code == 302
    assert get_url_path(redirected_to) == reverse(
        'dashboard:order-details',
        args=[order_with_lines_and_stock.pk])
    # success messages should appear after redirect
    assert response.context['messages']
    lines_after = Order.objects.get().get_lines()
    # order should have the same lines
    assert lines_before_quantity_change_count == lines_after.count()
    # stock allocation should be 2 now
    assert Stock.objects.first().quantity_allocated == 2
    line.refresh_from_db()
    # source line quantity should be decreased to 2
    assert line.quantity == 2
    # order should have the same shipment groups count
    assert order_with_lines_and_stock.groups.count() == 1
    # a note in the order's history should be created
    assert OrderHistoryEntry.objects.get(
        order=order_with_lines_and_stock).comment == (
            'Changed quantity for product %(product)s from'
            ' %(old_quantity)s to %(new_quantity)s') % {
                    'product': line.product,
                    'old_quantity': line_quantity_before_quantity_change,
                    'new_quantity': 2}


@pytest.mark.integration
@pytest.mark.django_db
def test_view_change_order_line_quantity_with_invalid_data(
        admin_client, order_with_lines_and_stock):
    """
    user goes to order details page
    user selects the first order line with quantity 3 and try to change it to 0 and -1
    user gets an error.
    """
    lines = order_with_lines_and_stock.get_lines()
    line = lines.first()
    url = reverse(
        'dashboard:orderline-change-quantity', kwargs={
            'order_pk': order_with_lines_and_stock.pk,
            'line_pk': line.pk})
    response = admin_client.post(
        url, {'quantity': 0})
    assert response.status_code == 400


def test_dashboard_change_quantity_form(request_cart_with_item, order):
    cart = request_cart_with_item
    group = DeliveryGroup.objects.create(order=order)
    fill_group_with_partition(group, cart.lines.all())
    order_line = group.lines.get()

    # Check max quantity validation
    form = ChangeQuantityForm({'quantity': 9999}, instance=order_line)
    assert not form.is_valid()
    assert form.errors['quantity'] == [
        'Ensure this value is less than or equal to 50.']

    # Check minimum quantity validation
    form = ChangeQuantityForm({'quantity': 0}, instance=order_line)
    assert not form.is_valid()
    assert group.lines.get().stock.quantity_allocated == 1

    # Check available quantity validation
    form = ChangeQuantityForm({'quantity': 20}, instance=order_line)
    assert not form.is_valid()
    assert group.lines.get().stock.quantity_allocated == 1
    assert form.errors['quantity'] == ['Only 5 remaining in stock.']

    # Save same quantity
    form = ChangeQuantityForm({'quantity': 1}, instance=order_line)
    assert form.is_valid()
    form.save()
    order_line.stock.refresh_from_db()
    assert group.lines.get().stock.quantity_allocated == 1

    # Increase quantity
    form = ChangeQuantityForm({'quantity': 2}, instance=order_line)
    assert form.is_valid()
    form.save()
    order_line.stock.refresh_from_db()
    assert group.lines.get().stock.quantity_allocated == 2

    # Decrease quantity
    form = ChangeQuantityForm({'quantity': 1}, instance=order_line)
    assert form.is_valid()
    form.save()
    assert group.lines.get().stock.quantity_allocated == 1


@pytest.mark.integration
@pytest.mark.django_db
def test_view_split_order_line(admin_client, order_with_lines_and_stock):
    """
    user goes to order details page
    user selects first order line with quantity 3 and moves 2 items
      to a new shipment
    user selects the line from the new shipment and moves all items
      back to the first shipment
    """
    lines_before_split = order_with_lines_and_stock.get_lines()
    lines_before_split_count = lines_before_split.count()
    line = lines_before_split.first()
    line_quantity_before_split = line.quantity
    quantity_allocated_before_split = line.stock.quantity_allocated
    old_delivery_group = DeliveryGroup.objects.get()

    url = reverse(
        'dashboard:orderline-split', kwargs={
            'order_pk': order_with_lines_and_stock.pk,
            'line_pk': line.pk})
    response = admin_client.get(url)
    assert response.status_code == 200
    response = admin_client.post(
        url,
        {'quantity': 2, 'target_group': ''},
        follow=True)
    redirected_to, redirect_status_code = response.redirect_chain[-1]
    # check redirection
    assert redirect_status_code == 302
    assert get_url_path(redirected_to) == reverse(
        'dashboard:order-details',
        args=[order_with_lines_and_stock.pk])
    # success messages should appear after redirect
    assert response.context['messages']
    lines_after = Order.objects.get().get_lines()
    # order should have one more line
    assert lines_before_split_count + 1 == lines_after.count()
    # stock allocation should not be changed
    assert Stock.objects.first().quantity_allocated == quantity_allocated_before_split
    line.refresh_from_db()
    # source line quantity should be decreased to 1
    assert line.quantity == line_quantity_before_split - 2
    # order should have 2 shipment groups now
    assert order_with_lines_and_stock.groups.count() == 2
    # a note in the order's history should be created
    new_group = DeliveryGroup.objects.last()
    assert OrderHistoryEntry.objects.get(
        order=order_with_lines_and_stock).comment == (
                'Moved 2 items %(item)s from '
                '%(old_group)s to %(new_group)s') % {
                    'item': line,
                    'old_group': old_delivery_group,
                    'new_group': new_group}
    new_line = new_group.lines.get()
    # the new line should contain the moved quantity
    assert new_line.quantity == 2
    url = reverse(
        'dashboard:orderline-split', kwargs={
            'order_pk': order_with_lines_and_stock.pk,
            'line_pk': new_line.pk})
    admin_client.post(
        url, {'quantity': 2, 'target_group': old_delivery_group.pk})
    # an other note in the order's history should be created
    assert OrderHistoryEntry.objects.filter(
        order=order_with_lines_and_stock).last().comment ==(
            'Moved 2 items %(item)s from removed '
            'group to %(new_group)s') % {
                'item': line,
                'new_group': old_delivery_group}
    # the new shipment should be removed
    assert order_with_lines_and_stock.groups.count() == 1
    # the related order line should be removed
    assert lines_before_split_count == Order.objects.get().get_lines().count()
    line.refresh_from_db()
    # the initial line should get the quantity restored to its initial value
    assert line_quantity_before_split == line.quantity


@pytest.mark.integration
@pytest.mark.django_db
@pytest.mark.parametrize('quantity', [0, 4])
def test_view_split_order_line_with_invalid_data(admin_client, order_with_lines_and_stock, quantity):
    """
    user goes to order details page
    user selects first order line with quantity 3 and try move 0 and 4 items to a new shipment
    user gets an error and no shipment groups are created.
    """
    lines = order_with_lines_and_stock.get_lines()
    line = lines.first()
    url = reverse(
        'dashboard:orderline-split', kwargs={
            'order_pk': order_with_lines_and_stock.pk,
            'line_pk': line.pk})
    response = admin_client.post(
        url, {'quantity': quantity, 'target_group': ''})
    assert response.status_code == 400
    assert DeliveryGroup.objects.count() == 1


def test_ordered_item_change_quantity(transactional_db, order_with_lines):
    assert list(order_with_lines.history.all()) == []
    lines = order_with_lines.groups.all()[0].lines.all()
    change_order_line_quantity(lines[0], 0)
    change_order_line_quantity(lines[1], 0)
    change_order_line_quantity(lines[2], 0)
    history = list(order_with_lines.history.all())
    assert len(history) == 1
    assert history[0].status == OrderStatus.CLOSED
    assert history[0].comment == 'Order cancelled. No items in order'


def test_ordered_item_remove_empty_group_with_force(
        transactional_db, order_with_lines):
    group = order_with_lines.groups.all()[0]
    lines = group.lines.all()
    remove_empty_groups(lines[0], force=True)
    history = list(order_with_lines.history.all())
    assert len(history) == 1
    assert history[0].status == OrderStatus.CLOSED
    assert history[0].comment == 'Order cancelled. No items in order'


@pytest.mark.integration
@pytest.mark.django_db
def test_view_order_invoice(
        admin_client, order_with_lines_and_stock, billing_address):
    """
    user goes to order details page
    user clicks on Invoice button
    user downloads the invoice as PDF file
    """
    order_with_lines_and_stock.shipping_address = billing_address
    order_with_lines_and_stock.billing_address = billing_address
    order_with_lines_and_stock.save()
    url = reverse(
        'dashboard:order-invoice', kwargs={
            'order_pk': order_with_lines_and_stock.id
        })
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response['content-type'] == 'application/pdf'
    name = "invoice-%s" % order_with_lines_and_stock.id
    assert response['Content-Disposition'] == 'filename=%s' % name


@pytest.mark.integration
@pytest.mark.django_db
def test_view_order_packing_slips(
        admin_client, order_with_lines_and_stock, billing_address):
    """
    user goes to order details page
    user clicks on Packing Slips button
    user downloads the packing slips as PDF file
    """
    order_with_lines_and_stock.shipping_address = billing_address
    order_with_lines_and_stock.billing_address = billing_address
    order_with_lines_and_stock.save()
    url = reverse(
        'dashboard:order-packing-slips', kwargs={
            'group_pk': order_with_lines_and_stock.groups.all()[0].pk
        })
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response['content-type'] == 'application/pdf'
    name = "packing-slip-%s-%s" % (
        order_with_lines_and_stock.id,
        order_with_lines_and_stock.groups.all()[0].pk)
    assert response['Content-Disposition'] == 'filename=%s' % name


@pytest.mark.integration
@pytest.mark.django_db
def test_view_change_order_line_stock_valid(
        admin_client, order_with_lines_and_stock):
    order = order_with_lines_and_stock
    line = order.get_lines().last()
    old_stock = line.stock
    variant = ProductVariant.objects.get(sku=line.product_sku)
    stock_location = StockLocation.objects.create(name='Warehouse 2')
    stock = Stock.objects.create(
        variant=variant, cost_price=2, quantity=2, quantity_allocated=0,
        location=stock_location)

    url = reverse(
        'dashboard:orderline-change-stock', kwargs={
            'order_pk': order.pk,
            'line_pk': line.pk})
    data = {'stock': stock.pk}
    response = admin_client.post(url, data)

    assert response.status_code == 200

    line.refresh_from_db()
    assert line.stock == stock
    assert line.stock_location == stock.location.name
    assert line.stock.quantity_allocated == 2

    old_stock.refresh_from_db()
    assert old_stock.quantity_allocated == 0


@pytest.mark.integration
@pytest.mark.django_db
def test_view_change_order_line_stock_insufficient_stock(
        admin_client, order_with_lines_and_stock):
    order = order_with_lines_and_stock
    line = order.get_lines().last()
    old_stock = line.stock
    variant = ProductVariant.objects.get(sku=line.product_sku)
    stock_location = StockLocation.objects.create(name='Warehouse 2')
    stock = Stock.objects.create(
        variant=variant, cost_price=2, quantity=2, quantity_allocated=1,
        location=stock_location)

    url = reverse(
        'dashboard:orderline-change-stock', kwargs={
            'order_pk': order.pk,
            'line_pk': line.pk})
    data = {'stock': stock.pk}
    response = admin_client.post(url, data)

    assert response.status_code == 400

    line.refresh_from_db()
    assert line.stock == old_stock
    assert line.stock_location == old_stock.location.name

    old_stock.refresh_from_db()
    assert old_stock.quantity_allocated == 2

    stock.refresh_from_db()
    assert stock.quantity_allocated == 1


def test_view_change_order_line_stock_merges_lines(
        admin_client, order_with_lines_and_stock):
    order = order_with_lines_and_stock
    line = order.get_lines().first()
    group = line.delivery_group
    old_stock = line.stock
    variant = ProductVariant.objects.get(sku=line.product_sku)
    stock_location = StockLocation.objects.create(name='Warehouse 2')
    stock = Stock.objects.create(
        variant=variant, cost_price=2, quantity=2, quantity_allocated=2,
        location=stock_location)
    line_2 = group.lines.create(
        delivery_group=group,
        product=line.product,
        product_name=line.product.name,
        product_sku='SKU_A',
        quantity=2,
        unit_price_net=Decimal('30.00'),
        unit_price_gross=Decimal('30.00'),
        stock=stock,
        stock_location=stock.location.name
    )
    lines_before = group.lines.count()

    url = reverse(
        'dashboard:orderline-change-stock', kwargs={
            'order_pk': order.pk,
            'line_pk': line_2.pk})
    data = {'stock': old_stock.pk}
    response = admin_client.post(url, data)

    assert response.status_code == 200
    assert group.lines.count() == lines_before - 1

    old_stock.refresh_from_db()
    assert old_stock.quantity_allocated == 5

    stock.refresh_from_db()
    assert stock.quantity_allocated == 0


def test_add_variant_to_existing_lines_one_line(
        order_with_variant_from_different_stocks):
    order = order_with_variant_from_different_stocks
    lines = order.get_lines().filter(product_sku='SKU_A')
    variant_lines_before = lines.count()
    line = lines.get(stock_location='Warehouse 2')
    quantity_before = line.quantity
    variant = ProductVariant.objects.get(sku='SKU_A')

    quantity_left = add_variant_to_existing_lines(
        line.delivery_group, variant, 2)

    lines_after = order.get_lines().filter(product_sku='SKU_A').count()
    line.refresh_from_db()
    assert quantity_left == 0
    assert lines_after == variant_lines_before
    assert line.quantity == 4


def test_add_variant_to_existing_lines_multiple_lines(
        order_with_variant_from_different_stocks):
    order = order_with_variant_from_different_stocks
    lines = order.get_lines().filter(product_sku='SKU_A')
    variant_lines_before = lines.count()
    line_1 = lines.get(stock_location='Warehouse 1')
    line_2 = lines.get(stock_location='Warehouse 2')
    variant = ProductVariant.objects.get(sku='SKU_A')

    quantity_left = add_variant_to_existing_lines(
        line_1.delivery_group, variant, 4)

    lines_after = order.get_lines().filter(product_sku='SKU_A').count()
    line_1.refresh_from_db()
    line_2.refresh_from_db()
    assert quantity_left == 0
    assert lines_after == variant_lines_before
    assert line_1.quantity == 4
    assert line_2.quantity == 5


def test_add_variant_to_existing_lines_multiple_lines_with_rest(
        order_with_variant_from_different_stocks):
    order = order_with_variant_from_different_stocks
    lines = order.get_lines().filter(product_sku='SKU_A')
    variant_lines_before = lines.count()
    line_1 = lines.get(stock_location='Warehouse 1')
    line_2 = lines.get(stock_location='Warehouse 2')
    variant = ProductVariant.objects.get(sku='SKU_A')

    quantity_left = add_variant_to_existing_lines(
        line_1.delivery_group, variant, 7)

    lines_after = order.get_lines().filter(product_sku='SKU_A').count()
    line_1.refresh_from_db()
    line_2.refresh_from_db()
    assert quantity_left == 2
    assert lines_after == variant_lines_before
    assert line_1.quantity == 5
    assert line_2.quantity == 5


def test_view_add_variant_to_delivery_group(
        admin_client, order_with_variant_from_different_stocks):
    order = order_with_variant_from_different_stocks
    group = order.groups.get()
    variant = ProductVariant.objects.get(sku='SKU_A')
    line = OrderLine.objects.get(
        product_sku='SKU_A', stock_location='Warehouse 2')
    url = reverse(
        'dashboard:add-variant-to-group', kwargs={
            'order_pk': order.pk, 'group_pk': group.pk})
    data = {'variant': variant.pk, 'quantity': 2}

    response = admin_client.post(url, data)

    line.refresh_from_db()
    assert response.status_code == 302
    assert get_redirect_location(response) == reverse(
        'dashboard:order-details', kwargs={'order_pk': order.pk})
    assert line.quantity == 4
