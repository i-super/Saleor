from graphene import relay

from ...page import models
from ..core.connection import CountableDjangoObjectType
from ..meta.deprecated.resolvers import resolve_meta, resolve_private_meta
from ..meta.types import ObjectWithMetadata
from ..translations.fields import TranslationField
from ..translations.types import PageTranslation


class Page(CountableDjangoObjectType):
    translation = TranslationField(PageTranslation, type_name="page")

    class Meta:
        description = (
            "A static page that can be manually added by a shop operator through the "
            "dashboard."
        )
        only_fields = [
            "content",
            "content_json",
            "created",
            "id",
            "is_published",
            "publication_date",
            "seo_description",
            "seo_title",
            "slug",
            "title",
        ]
        interfaces = [relay.Node, ObjectWithMetadata]
        model = models.Page

    @staticmethod
    def resolve_meta(root: models.Page, info):
        return resolve_meta(root, info)

    @staticmethod
    def resolve_private_meta(root: models.Page, _info):
        return resolve_private_meta(root, _info)
