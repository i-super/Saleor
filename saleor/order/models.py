from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import pgettext_lazy
from django_fsm import FSMField, transition
from django_prices.models import MoneyField, TaxedMoneyField
from payments import PaymentStatus, PurchasedItem
from payments.models import BasePayment
from prices import Money, TaxedMoney

from . import GroupStatus, OrderStatus
from ..account.models import Address
from ..core.utils import ZERO_TAXED_MONEY, build_absolute_uri
from ..discount.models import Voucher
from ..product.models import Product
from .transitions import (
    cancel_delivery_group, process_delivery_group, ship_delivery_group)


class OrderQuerySet(models.QuerySet):
    """Filters orders by status deduced from shipment groups."""

    def open(self):
        """Orders having at least one shipment group with status NEW."""
        return self.filter(Q(groups__status=GroupStatus.NEW))

    def closed(self):
        """Orders having no shipment groups with status NEW."""
        return self.filter(~Q(groups__status=GroupStatus.NEW))


class Order(models.Model):
    created = models.DateTimeField(
        default=now, editable=False)
    last_status_change = models.DateTimeField(
        default=now, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, related_name='orders',
        on_delete=models.SET_NULL)
    language_code = models.CharField(
        max_length=35, default=settings.LANGUAGE_CODE)
    tracking_client_id = models.CharField(
        max_length=36, blank=True, editable=False)
    billing_address = models.ForeignKey(
        Address, related_name='+', editable=False,
        on_delete=models.PROTECT)
    shipping_address = models.ForeignKey(
        Address, related_name='+', editable=False, null=True,
        on_delete=models.PROTECT)
    user_email = models.EmailField(
        blank=True, default='', editable=False)
    shipping_price_net = MoneyField(
        currency=settings.DEFAULT_CURRENCY, max_digits=12, decimal_places=2,
        default=0, editable=False)
    shipping_price_gross = MoneyField(
        currency=settings.DEFAULT_CURRENCY, max_digits=12, decimal_places=2,
        default=0, editable=False)
    shipping_price = TaxedMoneyField(
        net_field='shipping_price_net', gross_field='shipping_price_gross')
    token = models.CharField(max_length=36, unique=True)
    total_net = MoneyField(
        currency=settings.DEFAULT_CURRENCY, max_digits=12, decimal_places=2)
    total_gross = MoneyField(
        currency=settings.DEFAULT_CURRENCY, max_digits=12, decimal_places=2)
    total = TaxedMoneyField(net_field='total_net', gross_field='total_gross')
    voucher = models.ForeignKey(
        Voucher, null=True, related_name='+', on_delete=models.SET_NULL)
    discount_amount = MoneyField(
        currency=settings.DEFAULT_CURRENCY, max_digits=12, decimal_places=2,
        blank=True, null=True)
    discount_name = models.CharField(max_length=255, default='', blank=True)

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
        return super().save(*args, **kwargs)

    def get_lines(self):
        return OrderLine.objects.filter(delivery_group__order=self)

    def is_fully_paid(self):
        total_paid = sum(
            [
                payment.get_total_price() for payment in
                self.payments.filter(status=PaymentStatus.CONFIRMED)],
            TaxedMoney(
                net=Money(0, currency=settings.DEFAULT_CURRENCY),
                gross=Money(0, currency=settings.DEFAULT_CURRENCY)))
        return total_paid.gross >= self.total.gross

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
        return '#%d' % (self.id,)

    def get_absolute_url(self):
        return reverse('order:details', kwargs={'token': self.token})

    def get_last_payment_status(self):
        last_payment = self.payments.last()
        if last_payment:
            return last_payment.status
        return None

    def get_last_payment_status_display(self):
        last_payment = self.payments.last()
        if last_payment:
            return last_payment.get_status_display()
        return None

    def is_pre_authorized(self):
        return self.payments.filter(status=PaymentStatus.PREAUTH).exists()

    def is_shipping_required(self):
        return any(group.is_shipping_required() for group in self.groups.all())

    @property
    def status(self):
        """Order status deduced from shipment groups."""
        statuses = set([group.status for group in self.groups.all()])
        return (
            OrderStatus.OPEN if GroupStatus.NEW in statuses
            else OrderStatus.CLOSED)

    @property
    def is_open(self):
        return self.status == OrderStatus.OPEN

    def get_status_display(self):
        """Order status display text."""
        return dict(OrderStatus.CHOICES)[self.status]

    def get_subtotal(self):
        subtotal_iterator = (line.get_total() for line in self.get_lines())
        return sum(subtotal_iterator, ZERO_TAXED_MONEY)

    def can_cancel(self):
        return self.status == OrderStatus.OPEN


class DeliveryGroup(models.Model):
    """Represents a single shipment.

    A single order can consist of multiple shipment groups.
    """

    status = FSMField(
        max_length=32, default=GroupStatus.NEW, choices=GroupStatus.CHOICES,
        protected=True)
    order = models.ForeignKey(
        Order, related_name='groups', editable=False, on_delete=models.CASCADE)
    shipping_method_name = models.CharField(
        max_length=255, null=True, default=None, blank=True, editable=False)
    tracking_number = models.CharField(max_length=255, default='', blank=True)
    last_updated = models.DateTimeField(null=True, auto_now=True)

    def __str__(self):
        return pgettext_lazy(
            'Shipment group str', 'Shipment #%s') % self.pk

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __iter__(self):
        return iter(self.lines.all())

    @transition(
        field=status, source=GroupStatus.NEW, target=GroupStatus.NEW)
    def process(self, cart_lines, discounts=None):
        process_delivery_group(self, cart_lines, discounts)

    @transition(
        field=status, source=GroupStatus.NEW, target=GroupStatus.SHIPPED)
    def ship(self, tracking_number=''):
        ship_delivery_group(self, tracking_number)

    @transition(
        field=status,
        source=[GroupStatus.NEW, GroupStatus.SHIPPED],
        target=GroupStatus.CANCELLED)
    def cancel(self):
        cancel_delivery_group(self)

    def get_total_quantity(self):
        return sum([line.quantity for line in self])

    def is_shipping_required(self):
        return any([line.is_shipping_required for line in self.lines.all()])

    def can_ship(self):
        return self.is_shipping_required() and self.status == GroupStatus.NEW

    def can_cancel(self):
        return self.status != GroupStatus.CANCELLED

    def can_edit_lines(self):
        return self.status not in {GroupStatus.CANCELLED, GroupStatus.SHIPPED}

    def get_total(self):
        subtotals = [line.get_total() for line in self]
        if not subtotals:
            raise AttributeError(
                'Calling get_total() on an empty shipment group')
        return sum(subtotals[1:], subtotals[0])


class OrderLine(models.Model):
    delivery_group = models.ForeignKey(
        DeliveryGroup, related_name='lines', editable=False,
        on_delete=models.CASCADE)
    product = models.ForeignKey(
        Product, blank=True, null=True, related_name='+',
        on_delete=models.SET_NULL)
    product_name = models.CharField(max_length=128)
    product_sku = models.CharField(max_length=32)
    is_shipping_required = models.BooleanField()
    stock_location = models.CharField(max_length=100, default='')
    stock = models.ForeignKey(
        'product.Stock', on_delete=models.SET_NULL, null=True)
    quantity = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(999)])
    unit_price_net = MoneyField(
        currency=settings.DEFAULT_CURRENCY, max_digits=12, decimal_places=4)
    unit_price_gross = MoneyField(
        currency=settings.DEFAULT_CURRENCY, max_digits=12, decimal_places=4)
    unit_price = TaxedMoneyField(
        net_field='unit_price_net', gross_field='unit_price_gross')

    def __str__(self):
        return self.product_name

    def get_total(self):
        return self.unit_price * self.quantity


class PaymentQuerySet(models.QuerySet):
    def last(self):
        # using .all() here reuses data fetched by prefetch_related
        objects = list(self.all()[:1])
        if objects:
            return objects[0]
        return None


class Payment(BasePayment):
    order = models.ForeignKey(
        Order, related_name='payments', on_delete=models.PROTECT)

    objects = PaymentQuerySet.as_manager()

    class Meta:
        ordering = ('-pk',)

    def get_failure_url(self):
        return build_absolute_uri(
            reverse('order:details', kwargs={'token': self.order.token}))

    def get_success_url(self):
        return build_absolute_uri(
            reverse(
                'order:checkout-success', kwargs={'token': self.order.token}))

    def get_purchased_items(self):
        lines = [
            PurchasedItem(
                name=line.product_name, sku=line.product_sku,
                quantity=line.quantity,
                price=line.unit_price_gross.quantize(Decimal('0.01')).amount,
                currency=line.unit_price.currency)
            for line in self.order.get_lines()]

        voucher = self.order.voucher
        if voucher is not None:
            lines.append(
                PurchasedItem(
                    name=self.order.discount_name,
                    sku='DISCOUNT',
                    quantity=1,
                    price=-self.order.discount_amount.amount,
                    currency=self.order.discount_amount.currency))
        return lines

    def get_total_price(self):
        return TaxedMoney(
            net=Money(self.total - self.tax, currency=self.currency),
            gross=Money(self.total, currency=self.currency))

    def get_captured_price(self):
        return TaxedMoney(
            net=Money(self.captured_amount, currency=self.currency),
            gross=Money(self.captured_amount, currency=self.currency))


class OrderHistoryEntry(models.Model):
    date = models.DateTimeField(default=now, editable=False)
    order = models.ForeignKey(
        Order, related_name='history', on_delete=models.CASCADE)
    content = models.TextField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True,
        on_delete=models.SET_NULL)

    class Meta:
        ordering = ('date', )


class OrderNote(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True,
        on_delete=models.SET_NULL)
    date = models.DateTimeField(db_index=True, auto_now_add=True)
    order = models.ForeignKey(
        Order, related_name='notes', on_delete=models.CASCADE)
    content = models.TextField()
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ('date', )
