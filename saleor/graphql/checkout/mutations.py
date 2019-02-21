from datetime import date

import graphene
from django.db import transaction

from ...checkout import models
from ...checkout.utils import (
    add_variant_to_cart, add_voucher_to_cart, change_billing_address_in_cart,
    change_shipping_address_in_cart, create_order, get_or_create_user_cart,
    get_taxes_for_cart, get_voucher_for_cart, ready_to_place_order,
    recalculate_cart_discount, remove_voucher_from_cart)
from ...core import analytics
from ...core.exceptions import InsufficientStock
from ...core.utils.taxes import get_taxes_for_address
from ...discount import models as voucher_model
from ...payment import PaymentError
from ...payment.utils import gateway_process_payment
from ...shipping.models import ShippingMethod as ShippingMethodModel
from ..account.i18n import I18nMixin
from ..account.types import AddressInput, User
from ..core.mutations import BaseMutation, ModelMutation
from ..core.types.common import Error
from ..order.types import Order
from ..product.types import ProductVariant
from ..shipping.types import ShippingMethod
from .types import Checkout, CheckoutLine


def clean_shipping_method(
        checkout, method, errors, discounts, taxes, country_code=None,
        remove=True):
    # FIXME Add tests for this function
    if not method:
        return errors
    if not checkout.is_shipping_required():
        errors.append(
            Error(
                field='checkout',
                message='This checkout does not requires shipping.'))
    if not checkout.shipping_address:
        errors.append(
            Error(
                field='checkout',
                message=(
                    'Cannot choose a shipping method for a '
                    'checkout without the shipping address.')))
        return errors
    valid_methods = (
        ShippingMethodModel.objects.applicable_shipping_methods(
            price=checkout.get_subtotal(discounts, taxes).gross.amount,
            weight=checkout.get_total_weight(),
            country_code=country_code or checkout.shipping_address.country.code
        ))
    valid_methods = valid_methods.values_list('id', flat=True)
    if method.pk not in valid_methods and not remove:
        errors.append(
            Error(
                field='shippingMethod',
                message='Shipping method cannot be used with this checkout.'))
    if remove:
        checkout.shipping_method = None
        checkout.save(update_fields=['shipping_method'])
    return errors


def check_lines_quantity(variants, quantities):
    """Check if stock is sufficient for each line in the list of dicts.
    Return list of errors.
    """
    errors = []
    for variant, quantity in zip(variants, quantities):
        try:
            variant.check_quantity(quantity)
        except InsufficientStock as e:
            message = (
                'Could not add item '
                + '%(item_name)s. Only %(remaining)d remaining in stock.' % {
                    'remaining': e.item.quantity_available,
                    'item_name': e.item.display_product()})
            errors.append(('quantity', message))
    return errors


class CheckoutLineInput(graphene.InputObjectType):
    quantity = graphene.Int(
        required=True, description='The number of items purchased.')
    variant_id = graphene.ID(
        required=True, description='ID of the ProductVariant.')


class CheckoutCreateInput(graphene.InputObjectType):
    lines = graphene.List(
        CheckoutLineInput,
        description=(
            'A list of checkout lines, each containing information about '
            'an item in the checkout.'), required=True)
    email = graphene.String(
        description='The customer\'s email address.')
    shipping_address = AddressInput(
        description=(
            'The mailling address to where the checkout will be shipped.'))
    billing_address = AddressInput(
        description='Billing address of the customer.')


class CheckoutCreate(ModelMutation, I18nMixin):
    class Arguments:
        input = CheckoutCreateInput(
            required=True, description='Fields required to create checkout.')

    class Meta:
        description = 'Create a new checkout.'
        model = models.Cart
        return_field_name = 'checkout'

    @classmethod
    def clean_input(cls, info, instance, input, errors):
        cleaned_input = super().clean_input(info, instance, input, errors)
        user = info.context.user
        lines = input.pop('lines', None)
        if lines:
            variant_ids = [line.get('variant_id') for line in lines]
            variants = cls.get_nodes_or_error(
                ids=variant_ids, errors=errors, field='variant_id',
                only_type=ProductVariant)
            quantities = [line.get('quantity') for line in lines]
            if not errors:
                line_errors = check_lines_quantity(variants, quantities)
                if line_errors:
                    for err in line_errors:
                        cls.add_error(errors, field=err[0], message=err[1])
                else:
                    cleaned_input['variants'] = variants
                    cleaned_input['quantities'] = quantities

        default_shipping_address = None
        default_billing_address = None
        if user.is_authenticated:
            default_billing_address = user.default_billing_address
            default_shipping_address = user.default_shipping_address

        if 'shipping_address' in input:
            shipping_address, errors = cls.validate_address(
                input['shipping_address'], errors)
            cleaned_input['shipping_address'] = shipping_address
        else:
            cleaned_input['shipping_address'] = default_shipping_address

        if 'billing_address' in input:
            billing_address, errors = cls.validate_address(
                input['billing_address'], errors)
            cleaned_input['billing_address'] = billing_address
        else:
            cleaned_input['billing_address'] = default_billing_address

        # Use authenticated user's email as default email
        if user.is_authenticated:
            email = input.pop('email', None)
            cleaned_input['email'] = email or user.email

        return cleaned_input

    @classmethod
    def save(cls, info, instance, cleaned_input):
        shipping_address = cleaned_input.get('shipping_address')
        billing_address = cleaned_input.get('billing_address')
        if shipping_address:
            shipping_address.save()
            instance.shipping_address = shipping_address
        if billing_address:
            billing_address.save()
            instance.billing_address = billing_address

        instance.save()

        variants = cleaned_input.get('variants')
        quantities = cleaned_input.get('quantities')
        if variants and quantities:
            for variant, quantity in zip(variants, quantities):
                add_variant_to_cart(instance, variant, quantity)

    @classmethod
    def mutate(cls, root, info, input):
        errors = []
        user = info.context.user

        # `mutate` method is overriden to properly get or create a checkout
        # instance here:
        if user.is_authenticated:
            checkout = get_or_create_user_cart(user)
        else:
            checkout = models.Cart()

        cleaned_input = cls.clean_input(info, checkout, input, errors)
        checkout = cls.construct_instance(checkout, cleaned_input)
        cls.clean_instance(checkout, errors)
        if errors:
            return CheckoutCreate(errors=errors)
        cls.save(info, checkout, cleaned_input)
        cls._save_m2m(info, checkout, cleaned_input)
        return CheckoutCreate(checkout=checkout, errors=errors)


class CheckoutLinesAdd(BaseMutation):
    checkout = graphene.Field(Checkout, description='An updated Checkout.')

    class Arguments:
        checkout_id = graphene.ID(
            description='The ID of the Checkout.', required=True)
        lines = graphene.List(
            CheckoutLineInput,
            required=True,
            description=(
                'A list of checkout lines, each containing information about '
                'an item in the checkout.'))

    class Meta:
        description = 'Adds a checkout line to the existing checkout.'

    @classmethod
    def mutate(cls, root, info, checkout_id, lines, replace=False):
        errors = []
        checkout = cls.get_node_or_error(
            info, checkout_id, errors, 'checkout_id', only_type=Checkout)
        if checkout is None:
            return CheckoutLinesAdd(errors=errors)

        variants, quantities = None, None
        if lines:
            variant_ids = [line.get('variant_id') for line in lines]
            variants = cls.get_nodes_or_error(
                ids=variant_ids, errors=errors, field='variant_id',
                only_type=ProductVariant)
            quantities = [line.get('quantity') for line in lines]
            if not errors:
                line_errors = check_lines_quantity(variants, quantities)
                if line_errors:
                    for err in line_errors:
                        cls.add_error(errors, field=err[0], message=err[1])

        # FIXME test if below function is called
        clean_shipping_method(
            checkout=checkout, method=checkout.shipping_method,
            errors=errors, discounts=info.context.discounts,
            taxes=get_taxes_for_address(checkout.shipping_address))

        if errors:
            return CheckoutLinesAdd(errors=errors)

        if variants and quantities:
            for variant, quantity in zip(variants, quantities):
                add_variant_to_cart(
                    checkout, variant, quantity, replace=replace)

        recalculate_cart_discount(
            checkout, info.context.discounts, info.context.taxes)

        return CheckoutLinesAdd(checkout=checkout, errors=errors)


class CheckoutLinesUpdate(CheckoutLinesAdd):
    checkout = graphene.Field(Checkout, description='An updated Checkout.')

    class Meta:
        description = 'Updates CheckoutLine in the existing Checkout.'

    @classmethod
    def mutate(cls, root, info, checkout_id, lines):
        return super().mutate(root, info, checkout_id, lines, replace=True)


class CheckoutLineDelete(BaseMutation):
    checkout = graphene.Field(Checkout, description='An updated checkout.')

    class Arguments:
        checkout_id = graphene.ID(
            description='The ID of the Checkout.', required=True)
        line_id = graphene.ID(
            description='ID of the CheckoutLine to delete.')

    class Meta:
        description = 'Deletes a CheckoutLine.'

    @classmethod
    def mutate(cls, root, info, checkout_id, line_id):
        errors = []
        checkout = cls.get_node_or_error(
            info, checkout_id, errors, 'checkout_id', only_type=Checkout)
        line = cls.get_node_or_error(
            info, line_id, errors, 'line_id', only_type=CheckoutLine)

        if checkout is None or line is None:
            return CheckoutLineDelete(errors=errors)

        if line and line in checkout.lines.all():
            line.delete()

        # FIXME test if below function is called
        clean_shipping_method(
            checkout=checkout, method=checkout.shipping_method, errors=errors,
            discounts=info.context.discounts,
            taxes=get_taxes_for_address(checkout.shipping_address))
        if errors:
            return CheckoutLineDelete(errors=errors)

        recalculate_cart_discount(
            checkout, info.context.discounts, info.context.taxes)

        return CheckoutLineDelete(checkout=checkout, errors=errors)


class CheckoutCustomerAttach(BaseMutation):
    checkout = graphene.Field(Checkout, description='An updated checkout.')

    class Arguments:
        checkout_id = graphene.ID(
            required=True, description='ID of the Checkout.')
        customer_id = graphene.ID(
            required=True, description='The ID of the customer.')

    class Meta:
        description = 'Sets the customer as the owner of the Checkout.'

    @classmethod
    def mutate(cls, root, info, checkout_id, customer_id):
        errors = []
        checkout = cls.get_node_or_error(
            info, checkout_id, errors, 'checkout_id', only_type=Checkout)
        customer = cls.get_node_or_error(
            info, customer_id, errors, 'customer_id', only_type=User)
        if checkout is not None and customer:
            checkout.user = customer
            checkout.save(update_fields=['user'])
        return CheckoutCustomerAttach(checkout=checkout, errors=errors)


class CheckoutCustomerDetach(BaseMutation):
    checkout = graphene.Field(Checkout, description='An updated checkout')

    class Arguments:
        checkout_id = graphene.ID(description='Checkout ID', required=True)

    class Meta:
        description = 'Removes the user assigned as the owner of the checkout.'

    @classmethod
    def mutate(cls, root, info, checkout_id):
        errors = []
        checkout = cls.get_node_or_error(
            info, checkout_id, errors, 'checkout_id', only_type=Checkout)
        if checkout is not None and not checkout.user:
            cls.add_error(
                errors, field=None,
                message='There\'s no customer assigned to this Checkout.')
        if errors:
            return CheckoutCustomerDetach(errors=errors)

        checkout.user = None
        checkout.save(update_fields=['user'])
        return CheckoutCustomerDetach(checkout=checkout)


class CheckoutShippingAddressUpdate(BaseMutation, I18nMixin):
    checkout = graphene.Field(Checkout, description='An updated checkout')

    class Arguments:
        checkout_id = graphene.ID(description='ID of the Checkout.')
        shipping_address = AddressInput(
            description=(
                'The mailling address to where the checkout will be shipped.'))

    class Meta:
        description = 'Update shipping address in the existing Checkout.'

    @classmethod
    def mutate(cls, root, info, checkout_id, shipping_address):
        errors = []
        checkout = cls.get_node_or_error(
            info, checkout_id, errors, 'checkout_id', only_type=Checkout)

        if checkout is not None and shipping_address:
            shipping_address, errors = cls.validate_address(
                shipping_address, errors, instance=checkout.shipping_address)
            # FIXME test if below function is called
            clean_shipping_method(
                checkout, checkout.shipping_method, errors,
                info.context.discounts,
                get_taxes_for_address(shipping_address))
            if not errors:
                with transaction.atomic():
                    shipping_address.save()
                    change_shipping_address_in_cart(checkout, shipping_address)
                recalculate_cart_discount(
                    checkout, info.context.discounts, info.context.taxes)

        return CheckoutShippingAddressUpdate(checkout=checkout, errors=errors)


class CheckoutBillingAddressUpdate(CheckoutShippingAddressUpdate):
    checkout = graphene.Field(Checkout, description='An updated checkout')

    class Arguments:
        checkout_id = graphene.ID(description='ID of the Checkout.')
        billing_address = AddressInput(
            description=(
                'The billing address of the checkout.'))

    class Meta:
        description = 'Update billing address in the existing Checkout.'

    @classmethod
    def mutate(cls, root, info, checkout_id, billing_address):
        errors = []
        checkout = cls.get_node_or_error(
            info, checkout_id, errors, 'checkout_id', only_type=Checkout)

        if checkout is not None and billing_address:
            billing_address, errors = cls.validate_address(
                billing_address, errors, instance=checkout.billing_address)
            if not errors:
                with transaction.atomic():
                    billing_address.save()
                    change_billing_address_in_cart(checkout, billing_address)
        return CheckoutShippingAddressUpdate(checkout=checkout, errors=errors)


class CheckoutEmailUpdate(BaseMutation):
    checkout = graphene.Field(Checkout, description='An updated checkout')

    class Arguments:
        checkout_id = graphene.ID(description='Checkout ID')
        email = graphene.String(required=True, description='email')

    class Meta:
        description = 'Updates email address in the existing Checkout object.'

    @classmethod
    def mutate(cls, root, info, checkout_id, email):
        errors = []
        checkout = cls.get_node_or_error(
            info, checkout_id, errors, 'checkout_id', only_type=Checkout)
        if checkout is not None:
            checkout.email = email
            cls.clean_instance(checkout, errors)
            if errors:
                return CheckoutEmailUpdate(errors=errors)
            checkout.save(update_fields=['email'])

        return CheckoutEmailUpdate(checkout=checkout, errors=errors)


class CheckoutShippingMethodUpdate(BaseMutation):
    checkout = graphene.Field(Checkout, description='An updated checkout')

    class Arguments:
        checkout_id = graphene.ID(description='Checkout ID')
        shipping_method_id = graphene.ID(
            required=True, description='Shipping method')

    class Meta:
        description = 'Updates the shipping address of the checkout.'

    @classmethod
    def mutate(cls, root, info, checkout_id, shipping_method_id):
        errors = []
        checkout = cls.get_node_or_error(
            info, checkout_id, errors, 'checkout_id', only_type=Checkout)
        shipping_method = cls.get_node_or_error(
            info, shipping_method_id, errors, 'shipping_method_id',
            only_type=ShippingMethod)

        if checkout is not None and shipping_method:
            clean_shipping_method(
                checkout, shipping_method, errors, info.context.discounts,
                info.context.taxes, remove=False)

        if not errors:
            checkout.shipping_method = shipping_method
            checkout.save(update_fields=['shipping_method'])
            recalculate_cart_discount(
                checkout, info.context.discounts, info.context.taxes)

        return CheckoutShippingMethodUpdate(checkout=checkout, errors=errors)


class CheckoutComplete(BaseMutation):
    order = graphene.Field(Order, description='Placed order')

    class Arguments:
        checkout_id = graphene.ID(description='Checkout ID', required=True)

    class Meta:
        description = (
            'Completes the checkout. As a result a new order is created and '
            'a payment charge is made. This action requires a successful '
            'payment before it can be performed.')

    @classmethod
    def mutate(cls, root, info, checkout_id):
        errors = []
        checkout = cls.get_node_or_error(
            info, checkout_id, errors, 'checkout_id', only_type=Checkout)
        if checkout is None:
            return CheckoutComplete(errors=errors)

        taxes = get_taxes_for_cart(checkout, info.context.taxes)
        ready, checkout_error = ready_to_place_order(
            checkout, taxes, info.context.discounts)
        if not ready:
            cls.add_error(
                field=None, message=checkout_error, errors=errors)
            return CheckoutComplete(errors=errors)

        try:
            order = create_order(
                cart=checkout,
                tracking_code=analytics.get_client_id(info.context),
                discounts=info.context.discounts, taxes=taxes)
        except InsufficientStock:
            cls.add_error(
                field=None, message='Insufficient product stock.',
                errors=errors)
            return CheckoutComplete(errors=errors)

        payment = checkout.get_last_active_payment()
        try:
            gateway_process_payment(
                payment=payment, payment_token=payment.token)
        except PaymentError as e:
            cls.add_error(errors=errors, field=None, message=str(e))
        return CheckoutComplete(order=order, errors=errors)


class CheckoutUpdateVoucher(BaseMutation):
    checkout = graphene.Field(
        Checkout, description='An checkout with updated voucher')

    class Arguments:
        checkout_id = graphene.ID(description='Checkout ID', required=True)
        voucher_code = graphene.String(description='Voucher code')

    class Meta:
        description = (
            'Adds voucher to the checkout. '
            'Query it without voucher_code field to '
            'remove voucher from checkout.')

    @classmethod
    def mutate(cls, root, info, checkout_id, voucher_code=None):
        errors = []
        checkout = cls.get_node_or_error(
            info, checkout_id, errors, 'checkout_id', only_type=Checkout)
        if checkout is None:
            return CheckoutUpdateVoucher(errors=errors)

        if voucher_code:
            try:
                voucher = voucher_model.Voucher.objects.active(
                    date=date.today()).get(code=voucher_code)
            except voucher_model.Voucher.DoesNotExist:
                cls.add_error(
                    errors=errors,
                    field='voucher_code',
                    message='Voucher with given code does not exist.')
                return CheckoutUpdateVoucher(errors=errors)

            try:
                add_voucher_to_cart(voucher, checkout)
            except voucher_model.NotApplicable:
                cls.add_error(
                    errors=errors,
                    field='voucher_code',
                    message='Voucher is not applicable to that checkout.')
                return CheckoutUpdateVoucher(errors=errors)

        else:
            existing_voucher = get_voucher_for_cart(checkout)
            if existing_voucher:
                remove_voucher_from_cart(checkout)

        return CheckoutUpdateVoucher(checkout=checkout, errors=errors)
