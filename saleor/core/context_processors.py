from django.conf import settings

from ..product.models import Category


def get_setting_as_dict(name, short_name=None):
    short_name = short_name or name
    try:
        return {short_name: getattr(settings, name)}
    except AttributeError:
        return {}


def canonical_hostname(request):
    return get_setting_as_dict('CANONICAL_HOSTNAME')


def default_currency(request):
    return get_setting_as_dict('DEFAULT_CURRENCY')


def categories(request):
    return {'categories': Category.tree.root_nodes().filter(hidden=False)}
