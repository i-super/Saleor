from django.urls import reverse
from prices import Money

from saleor.shipping.models import ShippingZone, ShippingRate
from saleor.shipping import ShippingRateType


def test_shipping_zone_list(admin_client, shipping_zone):
    url = reverse('dashboard:shipping-zones')
    response = admin_client.get(url)
    assert response.status_code == 200


def test_shipping_zone_add(admin_client):
    assert ShippingZone.objects.count() == 0
    url = reverse('dashboard:shipping-zone-add')
    data = {'name': 'Zium', 'countries': ['PL']}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert ShippingZone.objects.count() == 1


def test_shipping_zone_add_not_valid(admin_client):
    assert ShippingZone.objects.count() == 0
    url = reverse('dashboard:shipping-zone-add')
    data = {}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert ShippingZone.objects.count() == 0


def test_shipping_zone_edit(admin_client, shipping_zone):
    assert ShippingZone.objects.count() == 1
    url = reverse('dashboard:shipping-zone-update',
                  kwargs={'pk': shipping_zone.pk})
    data = {'name': 'Flash', 'countries': ['PL']}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert ShippingZone.objects.count() == 1
    assert ShippingZone.objects.all()[0].name == 'Flash'


def test_shipping_zone_details(admin_client, shipping_zone):
    assert ShippingZone.objects.count() == 1
    url = reverse('dashboard:shipping-zone-details',
                  kwargs={'pk': shipping_zone.pk})
    response = admin_client.post(url, follow=True)
    assert response.status_code == 200


def test_shipping_zone_delete(admin_client, shipping_zone):
    assert ShippingZone.objects.count() == 1
    url = reverse('dashboard:shipping-zone-delete',
                  kwargs={'pk': shipping_zone.pk})
    response = admin_client.post(url, follow=True)
    assert response.status_code == 200
    assert ShippingZone.objects.count() == 0


def test_shipping_rate_add(admin_client, shipping_zone):
    assert ShippingRate.objects.count() == 1
    url = reverse('dashboard:shipping-rate-add',
                  kwargs={'shipping_zone_pk': shipping_zone.pk})
    data = {
        'name': 'DHL', 'price': '50', 'shipping_zone': shipping_zone.pk,
        'type': ShippingRateType.PRICE_BASED}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert ShippingRate.objects.count() == 2


def test_shipping_rate_add_not_valid(admin_client, shipping_zone):
    assert ShippingRate.objects.count() == 1
    url = reverse('dashboard:shipping-rate-add',
                  kwargs={'shipping_zone_pk': shipping_zone.pk})
    data = {}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert ShippingRate.objects.count() == 1


def test_shipping_rate_edit(admin_client, shipping_zone):
    assert ShippingRate.objects.count() == 1
    country = shipping_zone.shipping_rates.all()[0]
    assert country.price == Money(10, 'USD')
    url = reverse('dashboard:shipping-rate-edit',
                  kwargs={'shipping_zone_pk': shipping_zone.pk,
                          'shipping_rate_pk': country.pk})
    data = {
        'name': 'DHL', 'price': '50', 'shipping_zone': shipping_zone.pk,
        'type': ShippingRateType.PRICE_BASED}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert ShippingRate.objects.count() == 1

    shipping_price = shipping_zone.shipping_rates.all()[0].price
    assert shipping_price == Money(50, 'USD')


def test_shipping_rate_delete(admin_client, shipping_zone):
    assert ShippingRate.objects.count() == 1
    country = shipping_zone.shipping_rates.all()[0]
    url = reverse('dashboard:shipping-rate-delete',
                  kwargs={'shipping_zone_pk': shipping_zone.pk,
                          'shipping_rate_pk': country.pk})
    response = admin_client.post(url, follow=True)
    assert response.status_code == 200
    assert ShippingRate.objects.count() == 0
