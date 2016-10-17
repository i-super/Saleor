from __future__ import unicode_literals

import json

import pytest
from django.core.exceptions import ObjectDoesNotExist
from mock import MagicMock, Mock
from satchless.item import InsufficientStock

from saleor.cart import decorators, forms, utils, views
from saleor.cart.context_processors import cart_counter
from saleor.cart.models import Cart


@pytest.fixture
def cart(db):  # pylint: disable=I0011, W0613
    return Cart.objects.create()


def test_adding_without_checking(cart, product_in_stock):
    variant = product_in_stock.variants.get()
    cart.add(variant, 1000, check_quantity=False)
    assert len(cart) == 1


def test_adding_zero_quantity(cart, product_in_stock):
    variant = product_in_stock.variants.get()
    cart.add(variant, 0)
    assert len(cart) == 0


def test_adding_same_variant(cart, product_in_stock):
    variant = product_in_stock.variants.get()
    cart.add(variant, 1)
    cart.add(variant, 2)
    price_total = 10 * 3
    assert len(cart) == 1
    assert cart.count() == {'total_quantity': 3}
    assert cart.get_total().gross == price_total


def test_replacing_same_variant(cart, product_in_stock):
    variant = product_in_stock.variants.get()
    cart.add(variant, 1, replace=True)
    cart.add(variant, 2, replace=True)
    assert len(cart) == 1
    assert cart.count() == {'total_quantity': 2}


def test_adding_invalid_quantity(cart, product_in_stock):
    variant = product_in_stock.variants.get()
    with pytest.raises(ValueError):
        cart.add(variant, -1)


def test_getting_line(cart, product_in_stock):
    variant = product_in_stock.variants.get()
    assert cart.get_line(variant) is None
    line = cart.create_line(variant, 1, None)
    assert line == cart.get_line(variant)


def test_change_status(cart):
    with pytest.raises(ValueError):
        cart.change_status('spanish inquisition')

    cart.change_status(Cart.OPEN)
    assert cart.status == Cart.OPEN
    cart.change_status(Cart.CANCELED)
    assert cart.status == Cart.CANCELED


def test_shipping_detection(cart, product_in_stock):
    variant = product_in_stock.variants.get()
    assert not cart.is_shipping_required()
    cart.add(variant, 1, replace=True)
    assert cart.is_shipping_required()


def test_cart_counter(monkeypatch):
    monkeypatch.setattr('saleor.cart.context_processors.get_cart_from_request',
                        Mock(return_value=Mock(quantity=4)))
    ret = cart_counter(Mock())
    assert ret == {'cart_counter': 4}


def test_get_product_variants_and_prices():
    variant = Mock(product_id=1, id=1)
    cart = MagicMock()
    cart.__iter__.return_value = [
        Mock(quantity=1, variant=variant,
             get_price_per_item=Mock(return_value=10))]
    variants = list(utils.get_product_variants_and_prices(cart, variant))
    assert variants == [(variant, 10)]


def test_get_user_open_cart_token(monkeypatch):
    monkeypatch.setattr('saleor.cart.models.Cart.get_user_open_cart',
                        staticmethod(lambda x: None))
    assert decorators.get_user_open_cart_token(Mock()) is None

    token = 42
    monkeypatch.setattr('saleor.cart.models.Cart.get_user_open_cart',
                        staticmethod(lambda x: Mock(token=token)))
    assert decorators.get_user_open_cart_token(Mock()) == token


def test_find_and_assign_cart(cart, django_user_model):
    credentials = {'email': 'admin@example.com', 'password': 'admin'}
    user, _created = django_user_model.objects.get_or_create(
        email=credentials['email'], defaults={
            'is_active': True, 'is_staff': True, 'is_superuser': True})
    request = Mock(user=user, get_signed_cookie=lambda x, default: cart.token)
    response = Mock()

    assert cart not in user.carts.all()
    decorators.find_and_assign_cart(request, response)
    assert cart in user.carts.all()


def test_contains_unavailable_variants():
    missing_variant = Mock(
        check_quantity=Mock(side_effect=InsufficientStock('')))
    cart = MagicMock()
    cart.__iter__.return_value = [Mock(variant=missing_variant)]
    assert utils.contains_unavailable_variants(cart)

    variant = Mock(check_quantity=Mock())
    cart.__iter__.return_value = [Mock(variant=variant)]
    assert not utils.contains_unavailable_variants(cart)


def test_check_product_availability_and_warn(
        monkeypatch, cart, product_in_stock):
    variant = product_in_stock.variants.get()
    cart.add(variant, 1)
    monkeypatch.setattr('django.contrib.messages.warning',
                        Mock(warning=Mock()))
    monkeypatch.setattr('saleor.cart.utils.contains_unavailable_variants',
                        Mock(return_value=False))

    utils.check_product_availability_and_warn(MagicMock(), cart)
    assert len(cart) == 1

    monkeypatch.setattr('saleor.cart.utils.contains_unavailable_variants',
                        Mock(return_value=True))
    monkeypatch.setattr('saleor.cart.utils.remove_unavailable_variants',
                        lambda c: c.add(variant, 0, replace=True))

    utils.check_product_availability_and_warn(MagicMock(), cart)
    assert len(cart) == 0


def test_add_to_cart_form():
    cart_lines = []
    cart = Mock(add=lambda variant, quantity: cart_lines.append(variant),
                get_line=Mock(return_value=Mock(quantity=1)))
    data = {'quantity': 1}
    form = forms.AddToCartForm(data=data, cart=cart, product=Mock())

    product_variant = Mock(check_quantity=Mock(return_value=None))
    form.get_variant = Mock(return_value=product_variant)

    assert form.is_valid()
    form.save()
    assert cart_lines == [product_variant]

    with pytest.raises(NotImplementedError):
        data = {'quantity': 1}
        form = forms.AddToCartForm(data=data, cart=cart, product=Mock())
        form.is_valid()


def test_form_when_variant_does_not_exist():
    cart_lines = []
    cart = Mock(add=lambda variant, quantity: cart_lines.append(Mock()),
                get_line=Mock(return_value=Mock(quantity=1)))

    form = forms.AddToCartForm(data={'quantity': 1}, cart=cart, product=Mock())
    form.get_variant = Mock(side_effect=ObjectDoesNotExist)
    assert not form.is_valid()


def test_add_to_cart_form_when_empty_stock():
    cart_lines = []
    cart = Mock(add=lambda variant, quantity: cart_lines.append(Mock()),
                get_line=Mock(return_value=Mock(quantity=1)))

    form = forms.AddToCartForm(data={'quantity': 1}, cart=cart, product=Mock())
    exception_mock = InsufficientStock(
        Mock(get_stock_quantity=Mock(return_value=1)))
    product_variant = Mock(check_quantity=Mock(side_effect=exception_mock))
    form.get_variant = Mock(return_value=product_variant)
    assert not form.is_valid()


def test_add_to_cart_form_when_insufficient_stock():
    cart_lines = []
    cart = Mock(add=lambda variant, quantity: cart_lines.append(variant),
                get_line=Mock(return_value=Mock(quantity=1)))

    form = forms.AddToCartForm(data={'quantity': 1}, cart=cart, product=Mock())
    exception_mock = InsufficientStock(
        Mock(get_stock_quantity=Mock(return_value=4)))
    product_variant = Mock(check_quantity=Mock(side_effect=exception_mock))
    form.get_variant = Mock(return_value=product_variant)
    assert not form.is_valid()


def test_replace_cart_line_form(cart, product_in_stock):
    variant = product_in_stock.variants.get()
    initial_quantity = 1
    replaced_quantity = 4

    cart.add(variant, initial_quantity)
    data = {'quantity': replaced_quantity}
    form = forms.ReplaceCartLineForm(data=data, cart=cart, variant=variant)
    assert form.is_valid()
    form.save()
    assert cart.quantity == replaced_quantity


def test_replace_cartline_form_when_insufficient_stock(
        monkeypatch, cart, product_in_stock):
    variant = product_in_stock.variants.get()
    initial_quantity = 1
    replaced_quantity = 4

    cart.add(variant, initial_quantity)
    exception_mock = InsufficientStock(
        Mock(get_stock_quantity=Mock(return_value=2)))
    monkeypatch.setattr('saleor.product.models.ProductVariant.check_quantity',
                        Mock(side_effect=exception_mock))
    data = {'quantity': replaced_quantity}
    form = forms.ReplaceCartLineForm(data=data, cart=cart, variant=variant)
    assert not form.is_valid()
    with pytest.raises(KeyError):
        form.save()
    assert cart.quantity == initial_quantity


def test_view_empty_cart(monkeypatch, client, cart):
    monkeypatch.setattr(
        decorators, 'get_cart_from_request',
        lambda request: cart
    )
    request = client.get('/cart/')
    request.discounts = None
    response = views.index(request)  # pylint: disable=I0011, E1120
    assert response.status_code == 200


def test_view_cart(monkeypatch, client, cart, product_in_stock):
    variant = product_in_stock.variants.get()
    cart.add(variant, 1)
    monkeypatch.setattr(
        decorators, 'get_cart_from_request',
        lambda request: cart
    )
    request = client.get('/cart/')
    request.discounts = None
    response = views.index(request)  # pylint: disable=I0011, E1120
    assert response.status_code == 200


def test_view_update_cart_quantity(
        monkeypatch, client, cart, product_in_stock):
    variant = product_in_stock.variants.get()
    cart.add(variant, 1)
    monkeypatch.setattr(
        decorators, 'get_cart_from_request',
        lambda request: cart)
    request = client.post(
        '/cart/update/{}'.format(variant.pk), {'quantity': 3})
    request.discounts = None
    request.POST = {'quantity': 3}
    request.is_ajax = lambda: True
    # pylint: disable=I0011, E1120
    response = views.update(request, variant.pk)
    assert response.status_code == 200
    assert cart.quantity == 3


def test_view_invalid_update_cart(monkeypatch, client, cart, product_in_stock):
    variant = product_in_stock.variants.get()
    cart.add(variant, 1)
    monkeypatch.setattr(
        decorators, 'get_cart_from_request',
        lambda request: cart
    )
    request = client.post('/cart/update/{}'.format(variant.pk), {})
    request.discounts = None
    request.POST = {}
    request.is_ajax = lambda: True
    # pylint: disable=I0011, E1120
    response = views.update(request, variant.pk)
    resp_decoded = json.loads(response.content.decode('utf-8'))
    assert response.status_code == 400
    assert 'error' in resp_decoded.keys()
    assert cart.quantity == 1


def test_view_invalid_add_to_cart(monkeypatch, client, cart, product_in_stock):
    variant = product_in_stock.variants.get()
    initial_quantity = 1
    cart.add(variant, initial_quantity)
    monkeypatch.setattr(
        decorators, 'get_cart_from_request',
        lambda request, create: cart
    )
    request = client.post('/cart/add/{}'.format(variant.pk), {})
    request.discounts = None
    request.POST = {}
    request.user = Mock(is_authenticated=lambda: False)
    # pylint: disable=I0011, E1120
    response = views.add_to_cart(request, variant.pk)
    assert response.status_code == 302
    assert cart.quantity == initial_quantity


def test_view_add_to_cart(monkeypatch, client, cart, product_in_stock):
    variant = product_in_stock.variants.get()
    initial_quantity = 1
    cart.add(variant, initial_quantity)
    monkeypatch.setattr(
        decorators, 'get_cart_from_request',
        lambda request, create: cart)

    request = client.post('/cart/add/{}'.format(variant.pk), {})
    request.discounts = None
    request.POST = {'quantity': 1, 'variant': variant.pk}
    request.user = Mock(is_authenticated=lambda: False)
    # pylint: disable=I0011, E1120
    response = views.add_to_cart(request, variant.pk)
    assert response.status_code == 302
    assert cart.quantity == initial_quantity + 1
