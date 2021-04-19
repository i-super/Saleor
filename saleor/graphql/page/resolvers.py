import graphene

from ...core.tracing import traced_resolver
from ...page import models
from ..core.utils import from_global_id_or_error
from ..core.validators import validate_one_of_args_is_in_query
from .types import PageType


@traced_resolver
def resolve_page(info, global_page_id=None, slug=None):
    validate_one_of_args_is_in_query("id", global_page_id, "slug", slug)
    user = info.context.user

    if slug is not None:
        page = models.Page.objects.visible_to_user(user).filter(slug=slug).first()
    else:
        _type, page_pk = from_global_id_or_error(global_page_id)
        page = models.Page.objects.visible_to_user(user).filter(pk=page_pk).first()
    return page


@traced_resolver
def resolve_pages(info, **_kwargs):
    user = info.context.user
    return models.Page.objects.visible_to_user(user)


@traced_resolver
def resolve_page_type(info, global_page_type_id):
    return graphene.Node.get_node_from_global_id(info, global_page_type_id, PageType)


@traced_resolver
def resolve_page_types(info, **_kwargs):
    return models.PageType.objects.all()
