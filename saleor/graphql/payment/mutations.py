import graphene
from django.conf import settings
from graphql_jwt.decorators import permission_required
from prices import Money, TaxedMoney

from ...payment import PaymentError
from ...payment.utils import (
    create_payment_method, gateway_authorize, gateway_capture, gateway_refund,
    gateway_void)
from ..account.i18n import I18nMixin
from ..account.types import AddressInput
from ..checkout.types import Checkout
from ..core.mutations import BaseMutation
from ..core.types.common import Decimal
from .types import PaymentGatewayEnum, PaymentMethod


class PaymentMethodInput(graphene.InputObjectType):
    gateway = PaymentGatewayEnum()
    checkout_id = graphene.ID(description='Checkout ID.')
    transaction_token = graphene.String(
        required=True, description='One time transaction token.')
    amount = Decimal(
        required=True,
        description=(
            'Total amount of the transaction, including '
            'all taxes and discounts.'))
    billing_address = AddressInput(description='Billing address')


class CheckoutPaymentMethodCreate(BaseMutation, I18nMixin):
    payment_method = graphene.Field(
        PaymentMethod, description='Updated payment method')

    class Arguments:
        input = PaymentMethodInput(
            required=True, description='Payment method details')

    class Meta:
        description = 'Creates credit card transaction.'

    @classmethod
    def mutate(cls, root, info, input):
        # FIXME: improve error handling
        errors = []
        checkout = cls.get_node_or_error(
            info, input['checkout_id'], errors, 'checkout_id',
            only_type=Checkout)
        if not checkout:
            return CheckoutPaymentMethodCreate(errors=errors)
        billing_data = {}
        if input['billing_address']:
            billing_address, errors = cls.validate_address(
                input['billing_address'], errors, 'billing_address')
            if not billing_address:
                return CheckoutPaymentMethodCreate(errors=errors)
            billing_data = cls.clean_billing_address(billing_address)

        extra_data = cls.get_extra_info(info)
        gross = Money(input['amount'], currency=settings.DEFAULT_CURRENCY)
        payment_method = create_payment_method(
            total=gross,
            variant=input['gateway'], billing_email=checkout.email,
            extra_data=extra_data, checkout=checkout,
            **billing_data)

        # authorize payment
        try:
            gateway_authorize(payment_method, input['transaction_token'])
        except PaymentError as exc:
            msg = str(exc)
            cls.add_error(field=None, message=msg, errors=errors)

        return CheckoutPaymentMethodCreate(
            payment_method=payment_method, errors=errors)

    @classmethod
    def clean_billing_address(cls, billing_address):
        billing_data = {
            'billing_first_name': billing_address.first_name,
            'billing_last_name': billing_address.last_name,
            'billing_company_name': billing_address.company_name,
            'billing_address_1': billing_address.street_address_1,
            'billing_address_2': billing_address.street_address_2,
            'billing_city': billing_address.city,
            'billing_postal_code': billing_address.postal_code,
            'billing_country_code': billing_address.country,
            'billing_country_area': billing_address.country_area}
        return billing_data

    @classmethod
    def get_extra_info(cls, info):
        client_ip = info.context.META['REMOTE_ADDR']
        x_forwarded_for = info.context.META.get('HTTP_X_FORWARDED_FOR')
        user_agent = info.context.META.get('HTTP_USER_AGENT')
        customer_ip = x_forwarded_for if x_forwarded_for else client_ip
        return {
            'customer_ip_address': customer_ip,
            'customer_user_agent': user_agent}


class PaymentMethodCapture(BaseMutation):
    payment_method = graphene.Field(
        PaymentMethod, description='Updated payment method')

    class Arguments:
        payment_method_id = graphene.ID(
            required=True, description='Payment method ID')
        amount = Decimal(description='Transaction amount')

    class Meta:
        description = 'Captures the authorized payment amount'

    @classmethod
    @permission_required('order.manage_orders')
    def mutate(cls, root, info, payment_method_id, amount=None):
        errors = []
        payment_method = cls.get_node_or_error(
            info, payment_method_id, errors, 'payment_method_id',
            only_type=PaymentMethod)

        if not payment_method:
            return PaymentMethodCapture(errors=errors)

        try:
            gateway_capture(payment_method, amount)
        except PaymentError as exc:
            msg = str(exc)
            cls.add_error(field=None, message=msg, errors=errors)
        return PaymentMethodCapture(
            payment_method=payment_method, errors=errors)


class PaymentMethodRefund(PaymentMethodCapture):
    @classmethod
    @permission_required('order.manage_orders')
    def mutate(cls, root, info, payment_method_id, amount=None):
        errors = []
        payment_method = cls.get_node_or_error(
            info, payment_method_id, errors, 'payment_method_id',
            only_type=PaymentMethod)

        if not payment_method:
            return PaymentMethodRefund(errors=errors)

        try:
            gateway_refund(payment_method, amount=amount)
        except PaymentError as exc:
            msg = str(exc)
            cls.add_error(field=None, message=msg, errors=errors)
        return PaymentMethodRefund(
            payment_method=payment_method, errors=errors)

    class Meta:
        description = 'Refunds the captured payment amount'


class PaymentMethodVoid(BaseMutation):
    payment_method = graphene.Field(
        PaymentMethod, description='Updated payment method')

    class Arguments:
        payment_method_id = graphene.ID(
            required=True, description='Payment method ID')

    class Meta:
        description = 'Voids the authorized payment'

    @classmethod
    @permission_required('order.manage_orders')
    def mutate(cls, root, info, payment_method_id, amount=None):
        errors = []
        payment_method = cls.get_node_or_error(
            info, payment_method_id, errors, 'payment_method_id',
            only_type=PaymentMethod)

        if not payment_method:
            return PaymentMethodVoid(errors=errors)

        try:
            gateway_void(payment_method)
        except PaymentError as exc:
            msg = str(exc)
            cls.add_error(field=None, message=msg, errors=errors)
        return PaymentMethodVoid(payment_method=payment_method, errors=errors)
