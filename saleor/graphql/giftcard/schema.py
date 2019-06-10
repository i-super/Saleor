import graphene
from graphql_jwt.decorators import permission_required

from ...giftcard import models
from ..core.fields import PrefetchingConnectionField
from .mutations import (
    GiftCardActivate,
    GiftCardCreate,
    GiftCardDeactivate,
    GiftCardUpdate,
    GiftCardVerify,
)
from .resolvers import resolve_gift_card
from .types import GiftCard


class GiftCardQueries(graphene.ObjectType):
    gift_card = graphene.Field(
        GiftCard,
        id=graphene.Argument(graphene.ID, required=True),
        description="Lookup a gift card by ID.",
    )
    gift_cards = PrefetchingConnectionField(GiftCard, description="List of gift cards")

    def resolve_gift_card(self, info, **data):
        return resolve_gift_card(info, data.get("id"))

    @permission_required("giftcard.manage_gift_card")
    def resolve_gift_cards(self, info, **_kwargs):
        return models.GiftCard.objects.all()


class GiftCardMutations(graphene.ObjectType):
    gift_card_activate = GiftCardActivate.Field()
    gift_card_create = GiftCardCreate.Field()
    gift_card_deactivate = GiftCardDeactivate.Field()
    gift_card_update = GiftCardUpdate.Field()
    gift_card_verify = GiftCardVerify.Field()
