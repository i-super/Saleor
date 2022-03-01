import graphene

from ....checkout.error_codes import CheckoutErrorCode
from ....core.exceptions import PermissionDenied
from ....core.permissions import AccountPermissions
from ...core.descriptions import DEPRECATED_IN_3X_INPUT
from ...core.mutations import BaseMutation
from ...core.scalars import UUID
from ...core.types.common import CheckoutError
from ...core.validators import validate_one_of_args_is_in_mutation
from ...utils import get_user_or_app_from_context
from ..types import Checkout
from .utils import get_checkout_by_token


class CheckoutCustomerDetach(BaseMutation):
    checkout = graphene.Field(Checkout, description="An updated checkout.")

    class Arguments:
        checkout_id = graphene.ID(
            description=(
                f"The ID of the checkout. {DEPRECATED_IN_3X_INPUT} Use token instead."
            ),
            required=False,
        )
        token = UUID(description="Checkout token.", required=False)

    class Meta:
        description = "Removes the user assigned as the owner of the checkout."
        error_type_class = CheckoutError
        error_type_field = "checkout_errors"

    @classmethod
    def check_permissions(cls, context):
        return context.user.is_authenticated or context.app

    @classmethod
    def perform_mutation(cls, _root, info, checkout_id=None, token=None):
        # DEPRECATED
        validate_one_of_args_is_in_mutation(
            CheckoutErrorCode, "checkout_id", checkout_id, "token", token
        )

        if token:
            checkout = get_checkout_by_token(token)
        # DEPRECATED
        else:
            checkout = cls.get_node_or_error(
                info, checkout_id or token, only_type=Checkout, field="checkout_id"
            )

        requestor = get_user_or_app_from_context(info.context)
        if not requestor.has_perm(AccountPermissions.IMPERSONATE_USER):
            # Raise error if the current user doesn't own the checkout of the given ID.
            if checkout.user and checkout.user != info.context.user:
                raise PermissionDenied(
                    permissions=[AccountPermissions.IMPERSONATE_USER]
                )

        checkout.user = None
        checkout.save(update_fields=["user", "last_change"])

        info.context.plugins.checkout_updated(checkout)
        return CheckoutCustomerDetach(checkout=checkout)
