from __future__ import unicode_literals

from elasticsearch_dsl.query import MultiMatch
from ..documents import ProductDocument


def get_search_query(phrase):
    ''' Execute external search for product matching phrase  '''
    query = MultiMatch(fields=['title', 'name', 'description'], query=phrase)
    return (ProductDocument.search()
                           .query(query)
                           .source(False)
                           .filter('term', is_published=True))


def search(phrase, qs):
        return qs & get_search_query(phrase).to_queryset()
