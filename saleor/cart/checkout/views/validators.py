from functools import wraps

from django.core.exceptions import ValidationError
from django.shortcuts import redirect

from ....shipping.models import ShippingMethodCountry


def validate_cart(view):
    """Decorate a view making it require a non-empty cart.

    If the cart is empty redirects to the cart details.
    """
    @wraps(view)
    def func(request, cart):
        if cart:
            return view(request, cart)
        return redirect('cart:index')
    return func


def validate_shipping_address(view):
    """Decorate a view making it require a valid shipping address.

    If either the shipping address or customer email is empty, redirect to the
    shipping address step.

    Expects to be decorated with `@validate_cart`.
    """
    @wraps(view)
    def func(request, cart):
        if cart.user_email is None or cart.shipping_address is None:
            return redirect('cart:checkout-shipping-address')
        try:
            cart.shipping_address.full_clean()
        except ValidationError:
            return redirect('cart:checkout-shipping-address')
        return view(request, cart)
    return func


def validate_shipping_method(view):
    """Decorate a view making it require a shipping method.

    If the method is missing or incorrect, redirect to the shipping method
    step.

    Expects to be decorated with `@validate_cart`.
    """
    @wraps(view)
    def func(request, cart):
        if cart.shipping_method is None:
            return redirect('cart:checkout-shipping-method')
        country_code = cart.shipping_address.country.code
        valid_methods = ShippingMethodCountry.objects.select_related(
            'shipping_method').unique_for_country_code(country_code)
        if cart.shipping_method not in valid_methods:
            cart.shipping_method = None
            cart.save()
            return redirect('cart:checkout-shipping-method')
        return view(request, cart)
    return func


def validate_is_shipping_required(view):
    """Decorate a view making it check if cart in checkout needs shipping.

    If shipping is not needed, redirect to the checkout summary.

    Expects to be decorated with `@validate_cart`.
    """
    @wraps(view)
    def func(request, cart):
        if not cart.is_shipping_required():
            return redirect('cart:checkout-summary')
        return view(request, cart)
    return func
