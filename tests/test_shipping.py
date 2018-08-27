from unittest.mock import Mock

import pytest

from prices import Money, TaxedMoney
from saleor.core.utils import format_money
from saleor.shipping.utils import get_taxed_shipping_price


@pytest.mark.parametrize('price, charge_taxes, expected_price', [
    (Money(10, 'USD'), False, TaxedMoney(
        net=Money(10, 'USD'), gross=Money(10, 'USD'))),
    (Money(10, 'USD'), True, TaxedMoney(
        net=Money('8.13', 'USD'), gross=Money(10, 'USD')))])
def test_get_taxed_shipping_price(
        site_settings, vatlayer, price, charge_taxes, expected_price):
    site_settings.charge_taxes_on_shipping = charge_taxes
    site_settings.save()

    shipping_price = get_taxed_shipping_price(price, taxes=vatlayer)

    assert shipping_price == expected_price


def test_shipping_get_total_price(monkeypatch, shipping_zone, vatlayer):
    method = shipping_zone.shipping_methods.get()
    price = Money(10, 'USD')
    taxed_price = TaxedMoney(
        net=Money('8.13', 'USD'), gross=Money(10, 'USD'))
    mock_get_price = Mock(return_value=taxed_price)
    monkeypatch.setattr(
        'saleor.shipping.models.get_taxed_shipping_price', mock_get_price)
    method.get_total_price(taxes=vatlayer)
    mock_get_price.assert_called_once_with(price, vatlayer)


def test_shipping_get_ajax_label(shipping_zone):
    shipping_method = shipping_zone.shipping_methods.get()
    label = shipping_method.get_ajax_label()
    proper_label = '%(shipping_method)s %(price)s' % {
        'shipping_method': shipping_method,
        'price': format_money(shipping_method.price)}
    assert label == proper_label
