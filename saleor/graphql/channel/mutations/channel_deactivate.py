import graphene
from django.core.exceptions import ValidationError

from ....core.permissions import ChannelPermissions
from ...core.mutations import BaseMutation
from ...core.types import ChannelError, ChannelErrorCode
from ...plugins.dataloaders import load_plugin_manager
from ..types import Channel


class ChannelDeactivate(BaseMutation):
    channel = graphene.Field(Channel, description="Deactivated channel.")

    class Arguments:
        id = graphene.ID(required=True, description="ID of the channel to deactivate.")

    class Meta:
        description = "Deactivate a channel."
        permissions = (ChannelPermissions.MANAGE_CHANNELS,)
        error_type_class = ChannelError
        error_type_field = "channel_errors"

    @classmethod
    def clean_channel_availability(cls, channel):
        if channel.is_active is False:
            raise ValidationError(
                {
                    "id": ValidationError(
                        "This channel is already deactivated.",
                        code=ChannelErrorCode.INVALID,
                    )
                }
            )

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        channel = cls.get_node_or_error(info, data["id"], only_type=Channel)
        cls.clean_channel_availability(channel)
        channel.is_active = False
        channel.save(update_fields=["is_active"])
        manager = load_plugin_manager(info.context)
        cls.call_event(manager.channel_status_changed, channel)
        return ChannelDeactivate(channel=channel)
