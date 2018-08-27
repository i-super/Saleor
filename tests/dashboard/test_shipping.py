from django.urls import reverse
from prices import Money
from saleor.dashboard.shipping.forms import (
    ShippingMethodForm, ShippingZoneForm, currently_used_countries)
from saleor.shipping import ShippingMethodType
from saleor.shipping.models import ShippingMethod, ShippingZone


def test_currently_used_countries():
    zone_1 = ShippingZone.objects.create(name='Zone 1', countries=['PL'])
    zone_2 = ShippingZone.objects.create(name='Zone 2', countries=['DE'])
    result = currently_used_countries(zone_1.pk)
    assert list(result)[0][0] == 'DE'


def test_shipping_zone_form():
    zone_1 = ShippingZone.objects.create(name='Zone 1', countries=['PL'])
    zone_2 = ShippingZone.objects.create(name='Zone 2', countries=['DE'])
    form = ShippingZoneForm(
        instance=zone_1, data={'name': 'Zone 1', 'countries': ['PL']})

    assert 'DE' not in [
        code for code, name in form.fields['countries'].choices]
    assert form.is_valid()

    form = ShippingZoneForm(
        instance=zone_1, data={'name': 'Zone 2', 'countries': ['DE']})
    assert not form.is_valid()
    assert 'countries' in form.errors


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


def test_shipping_method_add(admin_client, shipping_zone):
    assert ShippingMethod.objects.count() == 1
    url = reverse(
        'dashboard:shipping-method-add', kwargs={
            'shipping_zone_pk': shipping_zone.pk, 'type': 'price'})
    data = {
        'name': 'DHL', 'price': '50', 'shipping_zone': shipping_zone.pk,
        'type': ShippingMethodType.PRICE_BASED}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert ShippingMethod.objects.count() == 2


def test_shipping_method_add_not_valid(admin_client, shipping_zone):
    assert ShippingMethod.objects.count() == 1
    url = reverse(
        'dashboard:shipping-method-add', kwargs={
            'shipping_zone_pk': shipping_zone.pk, 'type': 'price'})
    data = {}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert ShippingMethod.objects.count() == 1


def test_shipping_method_edit(admin_client, shipping_zone):
    assert ShippingMethod.objects.count() == 1
    country = shipping_zone.shipping_methods.all()[0]
    assert country.price == Money(10, 'USD')
    url = reverse('dashboard:shipping-method-edit',
                  kwargs={'shipping_zone_pk': shipping_zone.pk,
                          'shipping_method_pk': country.pk})
    data = {
        'name': 'DHL', 'price': '50', 'shipping_zone': shipping_zone.pk,
        'type': ShippingMethodType.PRICE_BASED}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert ShippingMethod.objects.count() == 1

    shipping_price = shipping_zone.shipping_methods.all()[0].price
    assert shipping_price == Money(50, 'USD')


def test_shipping_method_delete(admin_client, shipping_zone):
    assert ShippingMethod.objects.count() == 1
    country = shipping_zone.shipping_methods.all()[0]
    url = reverse('dashboard:shipping-method-delete',
                  kwargs={'shipping_zone_pk': shipping_zone.pk,
                          'shipping_method_pk': country.pk})
    response = admin_client.post(url, follow=True)
    assert response.status_code == 200
    assert ShippingMethod.objects.count() == 0
