from prices import Price

from saleor.cart.models import Cart
from saleor.order import models
from saleor.order.utils import add_items_to_delivery_group


def test_total_property():
    order = models.Order(total_net=20, total_tax=5)
    assert order.total.gross == 25
    assert order.total.tax == 5
    assert order.total.net == 20


def test_total_property_empty_value():
    order = models.Order(total_net=None, total_tax=None)
    assert order.total is None


def test_total_setter():
    price = Price(net=10, gross=20, currency='USD')
    order = models.Order()
    order.total = price
    assert order.total_net.net == 10
    assert order.total_tax.net == 10


def test_stock_allocation(billing_address, product_in_stock):
    variant = product_in_stock.variants.get()
    cart = Cart()
    cart.save()
    cart.add(variant, quantity=2)
    order = models.Order.objects.create(billing_address=billing_address)
    delivery_group = models.DeliveryGroup.objects.create(order=order)
    add_items_to_delivery_group(delivery_group, cart.lines.all())
    order_line = delivery_group.items.get()
    stock = order_line.stock
    assert stock.quantity_allocated == 2


def test_order_discount(sale, order, request_cart_with_item):
    cart = request_cart_with_item
    group = models.DeliveryGroup.objects.create(order=order)
    add_items_to_delivery_group(
        group, cart.lines.all(), discounts=cart.discounts)
    item = group.items.first()
    assert item.get_price_per_item() == Price(currency="USD", net=5)
