from __future__ import unicode_literals

from ..documents import ProductDocument, OrderDocument, UserDocument
from elasticsearch_dsl.query import MultiMatch


def _search_products(phrase):
    prod_query = MultiMatch(fields=['name', 'description'], query=phrase)
    return ProductDocument.search().query(prod_query).source(False)


def _search_users(phrase):
    user_query = MultiMatch(fields=['user'], query=phrase)
    return UserDocument.search().query(user_query).source(False)


def _search_orders(phrase):
    order_query = MultiMatch(
        fields=['user', 'status', 'discount_name'], query=phrase)
    return OrderDocument.search().query(order_query).source(False)


def get_search_queries(phrase):
    ''' Execute external search for all objects matching phrase  '''
    return {
        'products': _search_products(phrase),
        'users': _search_users(phrase),
        'orders': _search_orders(phrase)
    }


def search(phrase):
    ''' Provide queryset for every search result '''
    return {k: s.to_queryset() for k, s in get_search_queries(phrase).items()}
