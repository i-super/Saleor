from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import pgettext_lazy
from django_prices.models import PriceField
from payments import PaymentStatus, PurchasedItem
from payments.models import BasePayment
from prices import FixedDiscount, Price
from satchless.item import ItemLine, ItemSet

from . import emails, GroupStatus, OrderStatus
from ..core.utils import build_absolute_uri
from ..discount.models import Voucher
from ..product.models import Product
from ..userprofile.models import Address


class OrderQuerySet(models.QuerySet):
    """Filters orders by status deduced from shipment groups."""

    def open(self):
        """Orders having at least one NEW status in shipment groups."""
        return self.filter(Q(groups__status=GroupStatus.NEW))

    def closed(self):
        """Orders having any NEW status in shipment groups."""
        return self.filter(~Q(groups__status=GroupStatus.NEW))


class Order(models.Model, ItemSet):
    created = models.DateTimeField(
        pgettext_lazy('Order field', 'created'),
        default=now, editable=False)
    last_status_change = models.DateTimeField(
        pgettext_lazy('Order field', 'last status change'),
        default=now, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, related_name='orders',
        verbose_name=pgettext_lazy('Order field', 'user'),
        on_delete=models.SET_NULL)
    language_code = models.CharField(
        max_length=35, default=settings.LANGUAGE_CODE)
    tracking_client_id = models.CharField(
        pgettext_lazy('Order field', 'tracking client id'),
        max_length=36, blank=True, editable=False)
    billing_address = models.ForeignKey(
        Address, related_name='+', editable=False,
        verbose_name=pgettext_lazy('Order field', 'billing address'),
        on_delete=models.PROTECT)
    shipping_address = models.ForeignKey(
        Address, related_name='+', editable=False, null=True,
        verbose_name=pgettext_lazy('Order field', 'shipping address'),
        on_delete=models.PROTECT)
    user_email = models.EmailField(
        pgettext_lazy('Order field', 'user email'),
        blank=True, default='', editable=False)
    token = models.CharField(
        pgettext_lazy('Order field', 'token'), max_length=36, unique=True)
    total_net = PriceField(
        pgettext_lazy('Order field', 'total net'),
        currency=settings.DEFAULT_CURRENCY, max_digits=12, decimal_places=2,
        blank=True, null=True)
    total_tax = PriceField(
        pgettext_lazy('Order field', 'total tax'),
        currency=settings.DEFAULT_CURRENCY, max_digits=12, decimal_places=2,
        blank=True, null=True)
    voucher = models.ForeignKey(
        Voucher, null=True, related_name='+', on_delete=models.SET_NULL,
        verbose_name=pgettext_lazy('Order field', 'voucher'))
    discount_amount = PriceField(
        verbose_name=pgettext_lazy('Order field', 'discount amount'),
        currency=settings.DEFAULT_CURRENCY, max_digits=12, decimal_places=2,
        blank=True, null=True)
    discount_name = models.CharField(
        verbose_name=pgettext_lazy('Order field', 'discount name'),
        max_length=255, default='', blank=True)

    objects = OrderQuerySet.as_manager()

    class Meta:
        ordering = ('-last_status_change',)
        permissions = (
            ('view_order',
             pgettext_lazy('Permission description', 'Can view orders')),
            ('edit_order',
             pgettext_lazy('Permission description', 'Can edit orders')))

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = str(uuid4())
        return super(Order, self).save(*args, **kwargs)

    def get_lines(self):
        return OrderLine.objects.filter(delivery_group__order=self)

    def is_fully_paid(self):
        total_paid = sum(
            [payment.total for payment in
             self.payments.filter(status=PaymentStatus.CONFIRMED)], Decimal())
        total = self.get_total()
        return total_paid >= total.gross

    def get_user_current_email(self):
        return self.user.email if self.user else self.user_email

    def _index_billing_phone(self):
        return self.billing_address.phone

    def _index_shipping_phone(self):
        return self.shipping_address.phone

    def __iter__(self):
        return iter(self.groups.all())

    def __repr__(self):
        return '<Order #%r>' % (self.id,)

    def __str__(self):
        return '#%d' % (self.id, )

    @property
    def discount(self):
        return FixedDiscount(
            amount=self.discount_amount, name=self.discount_name)

    def get_total(self):
        return self.total

    def get_absolute_url(self):
        return reverse('order:details', kwargs={'token': self.token})

    def get_delivery_total(self):
        return sum(
            [group.shipping_price for group in self.groups.all()],
            Price(0, currency=settings.DEFAULT_CURRENCY))

    def send_confirmation_email(self):
        email = self.get_user_current_email()
        payment_url = build_absolute_uri(
            reverse('order:details', kwargs={'token': self.token}))
        emails.send_order_confirmation.delay(email, payment_url)

    def get_last_payment_status(self):
        last_payment = self.payments.last()
        if last_payment:
            return last_payment.status

    def get_last_payment_status_display(self):
        last_payment = self.payments.last()
        if last_payment:
            return last_payment.get_status_display()

    def is_pre_authorized(self):
        return self.payments.filter(status=PaymentStatus.PREAUTH).exists()

    def create_history_entry(self, comment='', status=None, user=None):
        if not status:
            status = self.status
        self.history.create(status=status, comment=comment, user=user)

    def is_shipping_required(self):
        return any(group.is_shipping_required() for group in self.groups.all())

    @property
    def status(self):
        """Order status deduced from shipment groups."""
        statuses = set([group.status for group in self.groups.all()])
        return (
            OrderStatus.OPEN if GroupStatus.NEW in statuses
            else OrderStatus.CLOSED
        )

    def get_status_display(self):
        """Order status display text."""
        return dict(OrderStatus.CHOICES)[self.status]

    @property
    def total(self):
        if self.total_net is not None:
            gross = self.total_net.net + self.total_tax.gross
            return Price(net=self.total_net.net, gross=gross,
                         currency=settings.DEFAULT_CURRENCY)

    @total.setter
    def total(self, price):
        self.total_net = price
        self.total_tax = Price(price.tax, currency=price.currency)

    def get_subtotal_without_voucher(self):
        if self.get_lines():
            return super(Order, self).get_total()
        return Price(net=0, currency=settings.DEFAULT_CURRENCY)

    def get_total_shipping(self):
        costs = [group.shipping_price for group in self]
        if costs:
            return sum(costs[1:], costs[0])
        return Price(net=0, currency=settings.DEFAULT_CURRENCY)

    def can_cancel(self):
        return self.status == OrderStatus.OPEN


class DeliveryGroup(models.Model, ItemSet):
    """Represents a single shipment.

    A single order can consist of many shipment groups.
    """
    status = models.CharField(
        pgettext_lazy('Shipment group field', 'shipment status'),
        max_length=32, default=GroupStatus.NEW, choices=GroupStatus.CHOICES)
    order = models.ForeignKey(
        Order, related_name='groups', editable=False, on_delete=models.CASCADE)
    shipping_price = PriceField(
        pgettext_lazy('Shipment group field', 'shipping price'),
        currency=settings.DEFAULT_CURRENCY, max_digits=12, decimal_places=4,
        default=0, editable=False)
    shipping_method_name = models.CharField(
        pgettext_lazy('Shipment group field', 'shipping method name'),
        max_length=255, null=True, default=None, blank=True, editable=False)
    tracking_number = models.CharField(
        pgettext_lazy('Shipment group field', 'tracking number'),
        max_length=255, default='', blank=True)
    last_updated = models.DateTimeField(
        pgettext_lazy('Shipment group field', 'last updated'),
        null=True, auto_now=True)

    def __str__(self):
        return pgettext_lazy(
            'Shipment group str', 'Shipment #%s') % self.pk

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __iter__(self):
        if self.id:
            return iter(self.lines.all())
        return super(DeliveryGroup, self).__iter__()

    @property
    def shipping_required(self):
        return self.shipping_method_name is not None

    def get_total_with_shipping(self, **kwargs):
        return self.get_total() + self.shipping_price

    def get_total_quantity(self):
        return sum([line.get_quantity() for line in self])

    def is_shipping_required(self):
        return self.shipping_required

    def can_ship(self):
        return self.is_shipping_required() and self.status == GroupStatus.NEW

    def can_cancel(self):
        return self.status != GroupStatus.CANCELLED

    def can_edit_lines(self):
        return self.status not in {GroupStatus.CANCELLED, GroupStatus.SHIPPED}


class OrderLine(models.Model, ItemLine):
    delivery_group = models.ForeignKey(
        DeliveryGroup, related_name='lines', editable=False,
        verbose_name=pgettext_lazy('Ordered line field', 'shipment group'),
        on_delete=models.CASCADE)
    product = models.ForeignKey(
        Product, blank=True, null=True, related_name='+',
        on_delete=models.SET_NULL,
        verbose_name=pgettext_lazy('Ordered line field', 'product'))
    product_name = models.CharField(
        pgettext_lazy('Ordered line field', 'product name'), max_length=128)
    product_sku = models.CharField(
        pgettext_lazy('Ordered line field', 'sku'), max_length=32)
    stock_location = models.CharField(
        pgettext_lazy('Ordered line field', 'stock location'), max_length=100,
        default='')
    stock = models.ForeignKey(
        'product.Stock', on_delete=models.SET_NULL, null=True,
        verbose_name=pgettext_lazy('Ordered line field', 'stock'))
    quantity = models.IntegerField(
        pgettext_lazy('Ordered line field', 'quantity'),
        validators=[MinValueValidator(0), MaxValueValidator(999)])
    unit_price_net = models.DecimalField(
        pgettext_lazy('Ordered line field', 'unit price (net)'),
        max_digits=12, decimal_places=4)
    unit_price_gross = models.DecimalField(
        pgettext_lazy('Ordered line field', 'unit price (gross)'),
        max_digits=12, decimal_places=4)

    def __str__(self):
        return self.product_name

    def get_price_per_item(self, **kwargs):
        return Price(net=self.unit_price_net, gross=self.unit_price_gross,
                     currency=settings.DEFAULT_CURRENCY)

    def get_quantity(self):
        return self.quantity


class PaymentManager(models.Manager):
    def last(self):
        # using .all() here reuses data fetched by prefetch_related
        objects = list(self.all()[:1])
        if objects:
            return objects[0]


class Payment(BasePayment):
    order = models.ForeignKey(
        Order, related_name='payments',
        verbose_name=pgettext_lazy('Payment field', 'order'),
        on_delete=models.PROTECT)

    objects = PaymentManager()

    class Meta:
        ordering = ('-pk',)

    def get_failure_url(self):
        return build_absolute_uri(
            reverse('order:details', kwargs={'token': self.order.token}))

    def get_success_url(self):
        return build_absolute_uri(
            reverse('order:create-password', kwargs={'token': self.order.token}))

    def send_confirmation_email(self):
        email = self.order.get_user_current_email()
        order_url = build_absolute_uri(
            reverse('order:details', kwargs={'token': self.order.token}))
        emails.send_payment_confirmation.delay(email, order_url)

    def get_purchased_items(self):
        lines = [
            PurchasedItem(
                name=line.product_name, sku=line.product_sku,
                quantity=line.quantity,
                price=line.unit_price_gross.quantize(Decimal('0.01')),
                currency=settings.DEFAULT_CURRENCY)
            for line in self.order.get_lines()]

        voucher = self.order.voucher
        if voucher is not None:
            lines.append(PurchasedItem(
                name=self.order.discount_name,
                sku='DISCOUNT',
                quantity=1,
                price=-self.order.discount_amount.net,
                currency=self.currency))
        return lines

    def get_total_price(self):
        net = self.total - self.tax
        return Price(net, gross=self.total, currency=self.currency)

    def get_captured_price(self):
        return Price(self.captured_amount, currency=self.currency)


class OrderHistoryEntry(models.Model):
    date = models.DateTimeField(
        pgettext_lazy('Order history entry field', 'last history change'),
        default=now, editable=False)
    order = models.ForeignKey(
        Order, related_name='history',
        verbose_name=pgettext_lazy('Order history entry field', 'order'),
        on_delete=models.CASCADE)
    status = models.CharField(
        pgettext_lazy('Order history entry field', 'order status'),
        max_length=32, choices=OrderStatus.CHOICES)
    comment = models.CharField(
        pgettext_lazy('Order history entry field', 'comment'),
        max_length=100, default='', blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True,
        verbose_name=pgettext_lazy('Order history entry field', 'user'),
        on_delete=models.SET_NULL)

    class Meta:
        ordering = ('date', )

    def __str__(self):
        return pgettext_lazy(
            'Order history entry str',
            'OrderHistoryEntry for Order #%d') % self.order.pk


class OrderNote(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    order = models.ForeignKey(
        Order, related_name='notes', on_delete=models.CASCADE)
    content = models.CharField(
        pgettext_lazy('Order note model', 'content'),
        max_length=250)

    def __str__(self):
        return pgettext_lazy(
            'Order note str',
            'OrderNote for Order #%d' % self.order.pk)
