from copy import deepcopy

import graphene
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from ...account.models import User
from ...core.permissions import GiftcardPermissions
from ...core.utils.promo_code import generate_promo_code
from ...core.utils.validators import is_date_in_future, user_is_valid
from ...giftcard import events, models
from ...giftcard.error_codes import GiftCardErrorCode
from ...giftcard.notifications import send_gift_card_notification
from ...giftcard.utils import activate_gift_card, deactivate_gift_card
from ..core.descriptions import ADDED_IN_31, DEPRECATED_IN_3X_INPUT
from ..core.mutations import BaseMutation, ModelDeleteMutation, ModelMutation
from ..core.scalars import PositiveDecimal
from ..core.types.common import GiftCardError, PriceInput
from ..core.utils import validate_required_string_field
from ..core.validators import validate_price_precision
from .types import GiftCard, GiftCardEvent


class GiftCardInput(graphene.InputObjectType):
    tag = graphene.String(description=f"{ADDED_IN_31} The gift card tag.")
    expiry_date = graphene.types.datetime.Date(
        description=f"{ADDED_IN_31} The gift card expiry date."
    )

    # DEPRECATED
    start_date = graphene.types.datetime.Date(
        description=(
            f"Start date of the gift card in ISO 8601 format. {DEPRECATED_IN_3X_INPUT}"
        )
    )
    end_date = graphene.types.datetime.Date(
        description=(
            "End date of the gift card in ISO 8601 format. "
            f"{DEPRECATED_IN_3X_INPUT} Use `expiryDate` from `expirySettings` instead."
        )
    )


class GiftCardCreateInput(GiftCardInput):
    balance = graphene.Field(
        PriceInput, description="Balance of the gift card.", required=True
    )
    user_email = graphene.String(
        required=False,
        description="Email of the customer to whom gift card will be sent.",
    )
    channel = graphene.String(
        description=(
            f"{ADDED_IN_31} Slug of a channel from which the email should be sent."
        )
    )
    is_active = graphene.Boolean(
        required=True, description=f"{ADDED_IN_31} Determine if gift card is active."
    )
    code = graphene.String(
        required=False,
        description=(
            "Code to use the gift card. "
            f"{DEPRECATED_IN_3X_INPUT} The code is now auto generated."
        ),
    )
    note = graphene.String(
        description=f"{ADDED_IN_31} The gift card note from the staff member."
    )


class GiftCardUpdateInput(GiftCardInput):
    balance_amount = PositiveDecimal(
        description=f"{ADDED_IN_31} The gift card balance amount.", required=False
    )


class GiftCardCreate(ModelMutation):
    class Arguments:
        input = GiftCardCreateInput(
            required=True, description="Fields required to create a gift card."
        )

    class Meta:
        description = "Creates a new gift card."
        model = models.GiftCard
        permissions = (GiftcardPermissions.MANAGE_GIFT_CARD,)
        error_type_class = GiftCardError
        error_type_field = "gift_card_errors"

    @classmethod
    def clean_input(cls, info, instance, data):
        cleaned_input = super().clean_input(info, instance, data)

        # perform only when gift card is created
        if instance.pk is None:
            cleaned_input["code"] = generate_promo_code()
            cls.set_created_by_user(cleaned_input, info)

        cls.clean_expiry_date(cleaned_input, instance)
        cls.clean_balance(cleaned_input, instance)

        if email := data.get("user_email"):
            try:
                validate_email(email)
            except ValidationError:
                raise ValidationError(
                    {
                        "email": ValidationError(
                            "Provided email is invalid.",
                            code=GiftCardErrorCode.INVALID.value,
                        )
                    }
                )
            if not data.get("channel"):
                raise ValidationError(
                    {
                        "channel": ValidationError(
                            "Channel slug must be specified "
                            "when user_email is provided.",
                            code=GiftCardErrorCode.REQUIRED.value,
                        )
                    }
                )
            cleaned_input["customer_user"] = User.objects.filter(email=email).first()

        return cleaned_input

    @staticmethod
    def set_created_by_user(cleaned_input, info):
        user = info.context.user
        if user_is_valid(user):
            cleaned_input["created_by"] = user
            cleaned_input["created_by_email"] = user.email
        cleaned_input["app"] = info.context.app

    @staticmethod
    def clean_expiry_date(cleaned_input, instance):
        expiry_date = cleaned_input.get("expiry_date")
        if expiry_date and not is_date_in_future(expiry_date):
            raise ValidationError(
                {
                    "expiry_date": ValidationError(
                        "Expiry date must be in the future.",
                        code=GiftCardErrorCode.INVALID.value,
                    )
                }
            )

    @staticmethod
    def clean_balance(cleaned_input, instance):
        balance = cleaned_input.pop("balance", None)
        if balance:
            amount = balance["amount"]
            currency = balance["currency"]
            try:
                validate_price_precision(amount, currency)
            except ValidationError as error:
                error.code = GiftCardErrorCode.INVALID.value
                raise ValidationError({"balance": error})
            if instance.pk:
                if currency != instance.currency:
                    raise ValidationError(
                        {
                            "balance": ValidationError(
                                "Cannot change gift card currency.",
                                code=GiftCardErrorCode.INVALID.value,
                            )
                        }
                    )
            if not amount > 0:
                raise ValidationError(
                    {
                        "balance": ValidationError(
                            "Balance amount have to be greater than 0.",
                            code=GiftCardErrorCode.INVALID.value,
                        )
                    }
                )
            cleaned_input["currency"] = currency
            cleaned_input["current_balance_amount"] = amount
            cleaned_input["initial_balance_amount"] = amount

    @classmethod
    def post_save_action(cls, info, instance, cleaned_input):
        user = info.context.user
        app = info.context.app
        events.gift_card_issued_event(
            gift_card=instance,
            user=user,
            app=app,
        )
        if note := cleaned_input.get("note"):
            events.gift_card_note_added_event(
                gift_card=instance, user=user, app=app, message=note
            )
        if email := cleaned_input.get("user_email"):
            send_gift_card_notification(
                cleaned_input.get("created_by"),
                cleaned_input.get("app"),
                cleaned_input["customer_user"],
                email,
                instance,
                info.context.plugins,
                channel_slug=cleaned_input["channel"],
                resending=False,
            )


class GiftCardUpdate(GiftCardCreate):
    class Arguments:
        id = graphene.ID(required=True, description="ID of a gift card to update.")
        input = GiftCardUpdateInput(
            required=True, description="Fields required to update a gift card."
        )

    class Meta:
        description = "Update a gift card."
        model = models.GiftCard
        permissions = (GiftcardPermissions.MANAGE_GIFT_CARD,)
        error_type_class = GiftCardError
        error_type_field = "gift_card_errors"

    @staticmethod
    def clean_balance(cleaned_input, instance):
        amount = cleaned_input.pop("balance_amount", None)

        if amount is None:
            return

        currency = instance.currency
        try:
            validate_price_precision(amount, currency)
        except ValidationError as error:
            error.code = GiftCardErrorCode.INVALID.value
            raise ValidationError({"balance_amount": error})
        cleaned_input["current_balance_amount"] = amount
        cleaned_input["initial_balance_amount"] = amount

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        instance = cls.get_instance(info, **data)
        old_instance = deepcopy(instance)

        data = data.get("input")
        cleaned_input = cls.clean_input(info, instance, data)
        instance = cls.construct_instance(instance, cleaned_input)
        cls.clean_instance(info, instance)
        cls.save(info, instance, cleaned_input)

        if "initial_balance_amount" in cleaned_input:
            events.gift_card_balance_reset_event(
                instance, old_instance, info.context.user, info.context.app
            )
        if "expiry_date" in cleaned_input:
            events.gift_card_expiry_date_updated_event(
                instance, old_instance, info.context.user, info.context.app
            )
        if "tag" in cleaned_input:
            events.gift_card_tag_updated_event(
                instance, old_instance, info.context.user, info.context.app
            )

        return cls.success_response(instance)


class GiftCardDelete(ModelDeleteMutation):
    class Arguments:
        id = graphene.ID(description="ID of the gift card to delete.", required=True)

    class Meta:
        description = f"{ADDED_IN_31} Delete gift card."
        model = models.GiftCard
        permissions = (GiftcardPermissions.MANAGE_GIFT_CARD,)
        error_type_class = GiftCardError
        error_type_field = "gift_card_errors"


class GiftCardDeactivate(BaseMutation):
    gift_card = graphene.Field(GiftCard, description="Deactivated gift card.")

    class Arguments:
        id = graphene.ID(required=True, description="ID of a gift card to deactivate.")

    class Meta:
        description = "Deactivate a gift card."
        permissions = (GiftcardPermissions.MANAGE_GIFT_CARD,)
        error_type_class = GiftCardError
        error_type_field = "gift_card_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        gift_card_id = data.get("id")
        gift_card = cls.get_node_or_error(
            info, gift_card_id, field="gift_card_id", only_type=GiftCard
        )
        # create event only when is_active value has changed
        create_event = gift_card.is_active
        deactivate_gift_card(gift_card)
        if create_event:
            events.gift_card_deactivated_event(
                gift_card=gift_card, user=info.context.user, app=info.context.app
            )
        return GiftCardDeactivate(gift_card=gift_card)


class GiftCardActivate(BaseMutation):
    gift_card = graphene.Field(GiftCard, description="Activated gift card.")

    class Arguments:
        id = graphene.ID(required=True, description="ID of a gift card to activate.")

    class Meta:
        description = "Activate a gift card."
        permissions = (GiftcardPermissions.MANAGE_GIFT_CARD,)
        error_type_class = GiftCardError
        error_type_field = "gift_card_errors"

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        gift_card_id = data.get("id")
        gift_card = cls.get_node_or_error(
            info, gift_card_id, field="gift_card_id", only_type=GiftCard
        )
        # create event only when is_active value has changed
        create_event = not gift_card.is_active
        activate_gift_card(gift_card)
        if create_event:
            events.gift_card_activated_event(
                gift_card=gift_card, user=info.context.user, app=info.context.app
            )
        return GiftCardActivate(gift_card=gift_card)


class GiftCardResendInput(graphene.InputObjectType):
    id = graphene.ID(required=True, description="ID of a gift card to resend.")
    email = graphene.String(
        required=False, description="Email to which gift card should be send."
    )
    channel = graphene.String(
        description="Slug of a channel from which the email should be sent.",
        required=True,
    )


class GiftCardResend(BaseMutation):
    gift_card = graphene.Field(GiftCard, description="Gift card which has been sent.")

    class Arguments:
        input = GiftCardResendInput(
            required=True, description="Fields required to resend a gift card."
        )

    class Meta:
        description = f"{ADDED_IN_31} Resend a gift card."
        permissions = (GiftcardPermissions.MANAGE_GIFT_CARD,)
        error_type_class = GiftCardError

    @classmethod
    def clean_input(cls, data):
        if email := data.get("email"):
            try:
                validate_email(email)
            except ValidationError:
                raise ValidationError(
                    {
                        "email": ValidationError(
                            "Provided email is invalid.",
                            code=GiftCardErrorCode.INVALID.value,
                        )
                    }
                )

        return data

    @classmethod
    def get_target_email(cls, data, gift_card):
        return (
            data.get("email") or gift_card.used_by_email or gift_card.created_by_email
        )

    @classmethod
    def get_customer_user(cls, email):
        return User.objects.filter(email=email).first()

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        data = data.get("input")
        data = cls.clean_input(data)
        gift_card_id = data["id"]
        gift_card = cls.get_node_or_error(
            info, gift_card_id, field="gift_card_id", only_type=GiftCard
        )
        target_email = cls.get_target_email(data, gift_card)
        customer_user = cls.get_customer_user(target_email)
        user = info.context.user
        if not user_is_valid(user):
            user = None
        send_gift_card_notification(
            user,
            info.context.app,
            customer_user,
            target_email,
            gift_card,
            info.context.plugins,
            channel_slug=data.get("channel"),
            resending=True,
        )
        return GiftCardResend(gift_card=gift_card)


class GiftCardAddNoteInput(graphene.InputObjectType):
    message = graphene.String(description="Note message.", required=True)


class GiftCardAddNote(BaseMutation):
    gift_card = graphene.Field(GiftCard, description="Gift card with the note added.")
    event = graphene.Field(GiftCardEvent, description="Gift card note created.")

    class Arguments:
        id = graphene.ID(
            required=True, description="ID of the gift card to add a note for."
        )
        input = GiftCardAddNoteInput(
            required=True,
            description="Fields required to create a note for the gift card.",
        )

    class Meta:
        description = f"{ADDED_IN_31} Adds note to the gift card."
        permissions = (GiftcardPermissions.MANAGE_GIFT_CARD,)
        error_type_class = GiftCardError

    @classmethod
    def clean_input(cls, _info, _instance, data):
        try:
            cleaned_input = validate_required_string_field(data["input"], "message")
        except ValidationError:
            raise ValidationError(
                {
                    "message": ValidationError(
                        "Message can't be empty.",
                        code=GiftCardErrorCode.REQUIRED,
                    )
                }
            )
        return cleaned_input

    @classmethod
    def perform_mutation(cls, _root, info, **data):
        gift_card = cls.get_node_or_error(info, data.get("id"), only_type=GiftCard)
        cleaned_input = cls.clean_input(info, gift_card, data)
        event = events.gift_card_note_added_event(
            gift_card=gift_card,
            user=info.context.user,
            app=info.context.app,
            message=cleaned_input["message"],
        )
        return GiftCardAddNote(gift_card=gift_card, event=event)
