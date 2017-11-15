import logging
from functools import wraps

from django.dispatch import receiver
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import pgettext_lazy
from payments.signals import status_changed

from ..core import analytics
from ..product.models import Stock
from ..userprofile.utils import store_user_address
from .models import Order
from . import OrderStatus

logger = logging.getLogger(__name__)


def check_order_status(func):
    @wraps(func)
    def decorator(*args, **kwargs):
        token = kwargs.pop('token')
        order = get_object_or_404(Order, token=token)
        if order.is_fully_paid():
            return redirect('order:details', token=order.token)
        kwargs['order'] = order
        return func(*args, **kwargs)

    return decorator


@receiver(status_changed)
def order_status_change(sender, instance, **kwargs):
    order = instance.order
    if order.is_fully_paid():
        order.change_status(OrderStatus.FULLY_PAID)
        order.create_history_entry(
            status=OrderStatus.FULLY_PAID, comment=pgettext_lazy(
                'Order status history entry', 'Order fully paid'))
        instance.send_confirmation_email()
        try:
            analytics.report_order(order.tracking_client_id, order)
        except Exception:
            # Analytics failing should not abort the checkout flow
            logger.exception('Recording order in analytics failed')


def attach_order_to_user(order, user):
    order.user = user
    store_user_address(user, order.billing_address, billing=True)
    if order.shipping_address:
        store_user_address(user, order.shipping_address, shipping=True)
    order.save(update_fields=['user'])


def add_items_to_delivery_group(delivery_group, partition, discounts=None):
    for item_line in partition:
        product_variant = item_line.variant
        price = item_line.get_price_per_item(discounts)
        total_quantity = item_line.get_quantity()

        while total_quantity > 0:
            stock = product_variant.select_stockrecord()
            quantity = (
                stock.quantity_available
                if stock and total_quantity > stock.quantity_available
                else total_quantity
            )
            delivery_group.items.create(
                product=product_variant.product,
                quantity=quantity,
                unit_price_net=price.net,
                product_name=product_variant.display_product(),
                product_sku=product_variant.sku,
                unit_price_gross=price.gross,
                stock=stock,
                stock_location=stock.location.name if stock else None)
            total_quantity -= quantity
            if stock:
                # allocate quantity to avoid overselling
                Stock.objects.allocate_stock(stock, quantity)


def cancel_delivery_group(group, cancel_order=True):
    for line in group:
        if line.stock:
            Stock.objects.deallocate_stock(line.stock, line.quantity)
    group.status = OrderStatus.CANCELLED
    group.save()
    if cancel_order:
        other_groups = group.order.groups.all()
        statuses = set(other_groups.values_list('status', flat=True))
        if statuses == {OrderStatus.CANCELLED}:
            # Cancel whole order
            group.order.status = OrderStatus.CANCELLED
            group.order.save(update_fields=['status'])


def cancel_order(order):
    for group in order.groups.all():
        cancel_delivery_group(group, cancel_order=False)
    order.status = OrderStatus.CANCELLED
    order.save()
