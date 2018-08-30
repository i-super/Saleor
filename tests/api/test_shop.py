import json
from unittest.mock import Mock

import graphene
from django.conf import settings
from django.shortcuts import reverse
from django_countries import countries
from django_prices_vatlayer.models import VAT
from tests.utils import get_graphql_content

from saleor.core.permissions import MODELS_PERMISSIONS
from saleor.site.models import Site

from .utils import assert_no_permission


def test_query_authorization_keys(authorization_key, admin_api_client, user_api_client):
    query = """
    query {
        shop {
            authorizationKeys {
                name
                key
            }
        }
    }
    """
    response = admin_api_client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['shop']
    assert data['authorizationKeys'][0]['name'] == authorization_key.name
    assert data['authorizationKeys'][0]['key'] == authorization_key.key

    response = user_api_client.post(reverse('api'), {'query': query})
    assert_no_permission(response)


def test_query_countries(user_api_client):
    query = """
    query {
        shop {
            countries {
                code
                country
            }
        }
    }
    """
    response = user_api_client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['shop']
    assert len(data['countries']) == len(countries)


def test_query_currencies(user_api_client):
    query = """
    query {
        shop {
            currencies
            defaultCurrency
        }
    }
    """
    response = user_api_client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['shop']
    assert len(data['currencies']) == len(settings.AVAILABLE_CURRENCIES)
    assert data['defaultCurrency'] == settings.DEFAULT_CURRENCY


def test_query_name(user_api_client, site_settings):
    query = """
    query {
        shop {
            name
            description
        }
    }
    """
    response = user_api_client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['shop']
    assert data['description'] == site_settings.description
    assert data['name'] == site_settings.site.name


def test_query_domain(user_api_client, site_settings):
    query = """
    query {
        shop {
            domain {
                host
                sslEnabled
                url
            }
        }
    }
    """
    response = user_api_client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['shop']
    assert data['domain']['host'] == site_settings.site.domain
    assert data['domain']['sslEnabled'] == settings.ENABLE_SSL
    assert data['domain']['url']


def test_query_tax_rates(admin_api_client, user_api_client, vatlayer):
    vat = VAT.objects.order_by('country_code').first()
    query = """
    query {
        shop {
            taxRates {
                countryCode
                standardRate
                reducedRates {
                    rate
                    rateType
                }
            }
        }
    }
    """
    response = admin_api_client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['shop']
    assert data['taxRates'][0]['countryCode'] == vat.country_code
    assert data['taxRates'][0]['standardRate'] == vat.data['standard_rate']
    assert len(data['taxRates'][0]['reducedRates']) == len(vat.data['reduced_rates'])

    response = user_api_client.post(reverse('api'), {'query': query})
    assert_no_permission(response)


def test_query_tax_rate(user_api_client, admin_api_client, vatlayer):
    vat = VAT.objects.order_by('country_code').first()
    query = """
    query taxRate($countryCode: String!) {
        shop {
            taxRate(countryCode: $countryCode) {
                countryCode
            }
        }
    }
    """
    variables = json.dumps({'countryCode': vat.country_code})
    response = admin_api_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['shop']
    assert data['taxRate']['countryCode'] == vat.country_code

    response = user_api_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    assert_no_permission(response)


def test_query_languages(settings, user_api_client):
    query = """
    query {
        shop {
            languages {
                code
                language
            }
        }
    }
    """
    response = user_api_client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['shop']
    assert len(data['languages']) == len(settings.LANGUAGES)


def test_query_permissions(admin_api_client, user_api_client):
    query = """
    query {
        shop {
            permissions {
                code
                name
            }
        }
    }
    """
    response = admin_api_client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['shop']
    permissions = data['permissions']
    permissions_codes = {permission.get('code') for permission in permissions}
    assert len(permissions_codes) == len(MODELS_PERMISSIONS)
    for code in permissions_codes:
        assert code in MODELS_PERMISSIONS

    response = user_api_client.post(reverse('api'), {'query': query})
    assert_no_permission(response)


def test_query_navigation(user_api_client, site_settings):
    query = """
    query {
        shop {
            navigation {
                main {
                    name
                }
                secondary {
                    name
                }
            }
        }
    }
    """
    response = user_api_client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    navigation_data = content['data']['shop']['navigation']
    assert navigation_data['main']['name'] == site_settings.top_menu.name
    assert navigation_data['secondary']['name'] == site_settings.bottom_menu.name



def test_shop_settings_mutation(admin_api_client, site_settings):
    query = """
        mutation updateSettings($input: ShopSettingsInput!) {
            shopSettingsUpdate(input: $input) {
                shop {
                    headerText,
                    includeTaxesInPrices
                }
            }
        }
    """
    variables = json.dumps({
        'input': {
            'includeTaxesInPrices': False,
            'headerText': 'Lorem ipsum'
        }
    })
    response = admin_api_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['shopSettingsUpdate']['shop']
    assert data['includeTaxesInPrices'] == False
    assert data['headerText'] == 'Lorem ipsum'
    site_settings.refresh_from_db()
    assert not site_settings.include_taxes_in_prices


def test_shop_domain_update(admin_api_client):
    query = """
        mutation updateSettings($domain: String!) {
            shopDomainUpdate(domain: $domain) {
                shop {
                    domain {
                        host
                    }
                }
            }
        }
    """
    variables = json.dumps({
        'domain': 'lorem-ipsum.com'
    })
    site = Site.objects.get_current()
    assert site.domain != 'lorem-ipsum.com'
    response = admin_api_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['shopDomainUpdate']['shop']
    assert data['domain']['host'] == 'lorem-ipsum.com'
    site.refresh_from_db()
    assert site.domain == 'lorem-ipsum.com'


def test_homepage_collection_update(admin_api_client, collection):
    query = """
        mutation homepageCollectionUpdate($collection: ID!) {
            homepageCollectionUpdate(collection: $collection) {
                shop {
                    homepageCollection {
                        id,
                        name
                    }
                }
            }
        }
    """
    collection_id = graphene.Node.to_global_id('Collection', collection.id)
    variables = json.dumps({
        'collection': collection_id
    })
    response = admin_api_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['homepageCollectionUpdate']['shop']
    assert data['homepageCollection']['id'] == collection_id
    assert data['homepageCollection']['name'] == collection.name
    site = Site.objects.get_current()
    assert site.settings.homepage_collection == collection



def test_shop_navigation_update(admin_api_client, menu):
    query = """
        mutation shopNavigationUpdate($input: ShopNavigationInput!) {
            shopNavigationUpdate(input: $input) {
                shop {
                    navigation {
                        main {
                            id,
                            name
                        }
                        secondary {
                            id,
                            name
                        }
                    }
                }
            }
        }
    """
    menu_id = graphene.Node.to_global_id('Menu', menu.id)
    variables = json.dumps({
        'input': {
            'main': menu_id}
    })
    site = Site.objects.get_current()
    old_top_menu = site.settings.top_menu
    old_bottom_menu = site.settings.bottom_menu
    old_bottom_menu_id = graphene.Node.to_global_id('Menu', old_bottom_menu.pk)
    assert old_top_menu != menu
    response = admin_api_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['shopNavigationUpdate']['shop']
    site.refresh_from_db()
    assert data['navigation']['main']['id'] == menu_id
    assert data['navigation']['main']['name'] == menu.name
    assert data['navigation']['secondary']['id'] == old_bottom_menu_id
    assert data['navigation']['secondary']['name'] == old_bottom_menu.name
    assert site.settings.top_menu == menu
    assert site.settings.bottom_menu == old_bottom_menu
