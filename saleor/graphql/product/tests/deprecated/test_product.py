import warnings

import graphene

from .....channel.utils import DEPRECATION_WARNING_MESSAGE
from .....product.models import Product
from ....tests.utils import get_graphql_content

QUERY_PRODUCT = """
    query ($id: ID, $slug: String){
        product(
            id: $id,
            slug: $slug,
        ) {
            id
            name
        }
    }
    """

QUERY_FETCH_ALL_PRODUCTS = """
    query {
        products(first: 1) {
            totalCount
            edges {
                node {
                    name
                }
            }
        }
    }
"""


def test_product_query_by_id_with_default_channel(user_api_client, product):
    variables = {"id": graphene.Node.to_global_id("Product", product.pk)}

    with warnings.catch_warnings(record=True) as warns:
        response = user_api_client.post_graphql(QUERY_PRODUCT, variables=variables)
        content = get_graphql_content(response)
    collection_data = content["data"]["product"]
    assert collection_data is not None
    assert collection_data["name"] == product.name
    assert any(
        [str(warning.message) == DEPRECATION_WARNING_MESSAGE for warning in warns]
    )


def test_product_query_by_slug_with_default_channel(user_api_client, product):
    variables = {"slug": product.slug}
    with warnings.catch_warnings(record=True) as warns:
        response = user_api_client.post_graphql(QUERY_PRODUCT, variables=variables)
        content = get_graphql_content(response)
    collection_data = content["data"]["product"]
    assert collection_data is not None
    assert collection_data["name"] == product.name
    assert any(
        [str(warning.message) == DEPRECATION_WARNING_MESSAGE for warning in warns]
    )


def test_fetch_all_products(user_api_client, product):
    with warnings.catch_warnings(record=True) as warns:
        response = user_api_client.post_graphql(QUERY_FETCH_ALL_PRODUCTS)
        content = get_graphql_content(response)
    num_products = Product.objects.count()
    assert content["data"]["products"]["totalCount"] == num_products
    assert len(content["data"]["products"]["edges"]) == num_products
    assert any(
        [str(warning.message) == DEPRECATION_WARNING_MESSAGE for warning in warns]
    )
