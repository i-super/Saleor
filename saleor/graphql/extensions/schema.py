import graphene

from ..core.fields import FilterInputConnectionField
from .filters import PluginFilterInput
from ..decorators import permission_required
from .mutations import PluginUpdate
from .resolvers import resolve_plugin, resolve_plugins
from .types import Plugin


class ExtensionsQueries(graphene.ObjectType):
    plugin = graphene.Field(
        Plugin,
        id=graphene.Argument(graphene.ID, required=True),
        description="Lookup a plugin by ID.",
    )
    plugins = FilterInputConnectionField(
        Plugin, filter=PluginFilterInput(), description="List of plugins"
    )

    @permission_required("extensions.manage_plugins")
    def resolve_plugin(self, info, **data):
        return resolve_plugin(info, data.get("id"))

    @permission_required("extensions.manage_plugins")
    def resolve_plugins(self, _info, **_kwargs):
        return resolve_plugins()


class ExtensionsMutations(graphene.ObjectType):
    plugin_update = PluginUpdate.Field()
