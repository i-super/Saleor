from django.urls import reverse

from .utils import get_redirect_location


def test_collection_index(customer_client, collection):
    url_kwargs = {'pk': collection.id, 'slug': collection.slug}
    url = reverse('product:collection', kwargs=url_kwargs)
    response = customer_client.get(url)
    assert response.status_code == 200


def test_collection_incorrect_slug(customer_client, collection):
    """When entered on the collection with proper PK but incorrect slug,
    one should be permanently(301) redirected to the proper url.
    """
    url_kwargs = {'pk': collection.id, 'slug': 'incorrect-slug'}
    url = reverse('product:collection', kwargs=url_kwargs)
    response = customer_client.get(url)
    # User should be redirected to the proper url
    assert response.status_code == 301

    redirected_url = get_redirect_location(response)
    proper_kwargs = {'pk': collection.id, 'slug': collection.slug}
    proper_url = reverse('product:collection', kwargs=proper_kwargs)
    assert redirected_url == proper_url

def test_collection_not_exists(customer_client):
    url_kwargs = {'pk': 123456, 'slug': 'incorrect-slug'}
    url = reverse('product:collection', kwargs=url_kwargs)
    response = customer_client.get(url)
    assert response.status_code == 404
