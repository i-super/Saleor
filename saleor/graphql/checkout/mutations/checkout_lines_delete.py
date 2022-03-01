import graphene
from django.core.exceptions import ValidationError

from ....checkout.fetch import fetch_checkout_info, fetch_checkout_lines
from ....checkout.utils import recalculate_checkout_discount
from ...core.mutations import BaseMutation
from ...core.scalars import UUID
from ...core.types.common import CheckoutError
from ...utils import resolve_global_ids_to_primary_keys
from ..types import Checkout
from .utils import get_checkout_by_token, update_checkout_shipping_method_if_invalid


class CheckoutLinesDelete(BaseMutation):
    checkout = graphene.Field(Checkout, description="An updated checkout.")

    class Arguments:
        token = UUID(description="Checkout token.", required=True)
        lines_ids = graphene.List(
            graphene.ID,
            required=True,
            description="A list of checkout lines.",
        )

    class Meta:
        description = "Deletes checkout lines."
        error_type_class = CheckoutError

    @classmethod
    def validate_lines(cls, checkout, lines_to_delete):
        lines = checkout.lines.all()
        all_lines_ids = [str(line.id) for line in lines]
        invalid_line_ids = list()
        for line_to_delete in lines_to_delete:
            if line_to_delete not in all_lines_ids:
                line_to_delete = graphene.Node.to_global_id(
                    "CheckoutLine", line_to_delete
                )
                invalid_line_ids.append(line_to_delete)

        if invalid_line_ids:
            raise ValidationError(
                {
                    "line_id": ValidationError(
                        "Provided line_ids aren't part of checkout.",
                        params={"lines": invalid_line_ids},
                    )
                }
            )

    @classmethod
    def perform_mutation(cls, _root, info, lines_ids, token=None):
        checkout = get_checkout_by_token(token)

        _, lines_to_delete = resolve_global_ids_to_primary_keys(
            lines_ids, graphene_type="CheckoutLine", raise_error=True
        )
        cls.validate_lines(checkout, lines_to_delete)
        checkout.lines.filter(id__in=lines_to_delete).delete()

        lines, _ = fetch_checkout_lines(checkout)

        manager = info.context.plugins
        checkout_info = fetch_checkout_info(
            checkout, lines, info.context.discounts, manager
        )
        update_checkout_shipping_method_if_invalid(checkout_info, lines)
        recalculate_checkout_discount(
            manager, checkout_info, lines, info.context.discounts
        )
        manager.checkout_updated(checkout)
        return CheckoutLinesDelete(checkout=checkout)
