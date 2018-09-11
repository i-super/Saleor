import graphene
from graphene import relay
from graphene_django import DjangoObjectType

from ...order import models
from ..core.types.common import CountableDjangoObjectType
from ..core.types.money import Money, TaxedMoney


class Fulfillment(CountableDjangoObjectType):
    status_display = graphene.String(
        description='User-friendly fulfillment status.')

    class Meta:
        description = 'Represents order fulfillment.'
        interfaces = [relay.Node]
        model = models.Fulfillment
        exclude_fields = ['order']

    def resolve_status_display(self, info):
        return self.get_status_display()


class FulfillmentLine(CountableDjangoObjectType):
    class Meta:
        description = 'Represents line of the fulfillment.'
        interfaces = [relay.Node]
        model = models.FulfillmentLine
        exclude_fields = ['fulfillment']


class Order(CountableDjangoObjectType):
    fulfillments = graphene.List(
        Fulfillment,
        required=True,
        description='List of shipments for the order.')
    is_paid = graphene.Boolean(
        description='Informs if an order is fully paid.')
    number = graphene.String(description='User-friendly number of an order.')
    payment_status = graphene.String(description='Internal payment status.')
    payment_status_display = graphene.String(
        description='User-friendly payment status.')
    subtotal = graphene.Field(
        TaxedMoney,
        description='The sum of line prices not including shipping.')
    status_display = graphene.String(description='User-friendly order status.')
    total_authorized = graphene.Field(
        Money, description='Amount authorized for the order.')
    total_captured = graphene.Field(
        Money, description='Amount captured by payment.')

    class Meta:
        description = 'Represents an order in the shop.'
        interfaces = [relay.Node]
        model = models.Order
        exclude_fields = [
            'shipping_price_gross', 'shipping_price_net', 'total_gross',
            'total_net']

    @staticmethod
    def resolve_subtotal(obj, info):
        return obj.get_subtotal()

    @staticmethod
    def resolve_total_authorized(obj, info):
        payment = obj.get_last_payment()
        if payment:
            return payment.get_total_price().gross

    @staticmethod
    def resolve_total_captured(obj, info):
        payment = obj.get_last_payment()
        if payment:
            return payment.get_captured_price()

    @staticmethod
    def resolve_fulfillments(obj, info):
        return obj.fulfillments.all()

    @staticmethod
    def resolve_is_paid(obj, info):
        return obj.is_fully_paid()

    @staticmethod
    def resolve_number(obj, info):
        return str(obj.pk)

    @staticmethod
    def resolve_payment_status(obj, info):
        return obj.get_last_payment_status()

    @staticmethod
    def resolve_payment_status_display(obj, info):
        return obj.get_last_payment_status_display()

    @staticmethod
    def resolve_status_display(obj, info):
        return obj.get_status_display()

    @staticmethod
    def resolve_user_email(obj, info):
        if obj.user_email:
            return obj.user_email
        if obj.user_id:
            return obj.user.email


class OrderHistoryEntry(CountableDjangoObjectType):
    class Meta:
        description = 'History log of the order.'
        model = models.OrderHistoryEntry
        interfaces = [relay.Node]
        exclude_fields = ['order']


class OrderLine(CountableDjangoObjectType):
    class Meta:
        description = 'Represents order line of particular order.'
        model = models.OrderLine
        interfaces = [relay.Node]
        exclude_fields = [
            'order', 'unit_price_gross', 'unit_price_net', 'variant']


class OrderNote(CountableDjangoObjectType):
    class Meta:
        description = 'Note from customer or staff user.'
        model = models.OrderNote
        interfaces = [relay.Node]
        exclude_fields = ['order']
