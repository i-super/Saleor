import json

import pytest

from django.contrib.sites.models import Site

from saleor.order.emails_helpers import (
    get_order_confirmation_markup, get_organization, get_product_data)


def test_get_organization(site_settings):
    example_name = 'Saleor Brand Name'
    site = Site.objects.get_current()
    site.name = example_name
    site.save()

    result = get_organization()
    assert result['name'] == example_name


def test_get_product_data_without_image(order_with_lines):
    """Tested OrderLine Product has no image assigned."""
    order_line = order_with_lines.get_lines()[0]
    currency = order_with_lines.total.currency
    organization = get_organization()

    result = get_product_data(order_line, currency, organization)
    assert 'image' not in result['itemOffered']


def test_get_product_data_with_image(delivery_group, product_with_image):
    order = delivery_group.order
    order_line = delivery_group.order.get_lines()[0]
    order_line.product = product_with_image
    order_line.product_name = product_with_image.name
    order_line.save()

    currency = order.total.currency
    organization = get_organization()

    result = get_product_data(order_line, currency, organization)
    assert 'image' in result['itemOffered']
    assert result['itemOffered']['name'] == product_with_image.name


def test_get_order_confirmation_markup(order_with_lines):
    try:
        result = get_order_confirmation_markup(order_with_lines)
    except TypeError:
        pytest.fail('Function output is not JSON serializable')

    try:
        # Response should be returned as a valid json
        json.loads(result)
    except ValueError:
        pytest.fail('Response is not a valid json')
