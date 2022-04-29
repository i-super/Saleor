import graphene

from ...core.permissions import OrderPermissions
from ..core.connection import create_connection_slice, filter_connection_queryset
from ..core.fields import FilterConnectionField, PermissionsField
from ..core.utils import from_global_id_or_error
from .filters import PaymentFilterInput
from .mutations import (
    PaymentCapture,
    PaymentCheckBalance,
    PaymentInitialize,
    PaymentRefund,
    PaymentVoid,
    TransactionCreate,
    TransactionRequestAction,
    TransactionUpdate,
)
from .resolvers import resolve_payment_by_id, resolve_payments
from .types import Payment, PaymentCountableConnection


class PaymentQueries(graphene.ObjectType):
    payment = PermissionsField(
        Payment,
        description="Look up a payment by ID.",
        id=graphene.Argument(
            graphene.ID, description="ID of the payment.", required=True
        ),
        permissions=[
            OrderPermissions.MANAGE_ORDERS,
        ],
    )
    payments = FilterConnectionField(
        PaymentCountableConnection,
        filter=PaymentFilterInput(description="Filtering options for payments."),
        description="List of payments.",
        permissions=[
            OrderPermissions.MANAGE_ORDERS,
        ],
    )

    def resolve_payment(self, info, **data):
        _, id = from_global_id_or_error(data["id"], Payment)
        return resolve_payment_by_id(id)

    def resolve_payments(self, info, **kwargs):
        qs = resolve_payments(info)
        qs = filter_connection_queryset(qs, kwargs)
        return create_connection_slice(qs, info, kwargs, PaymentCountableConnection)


class PaymentMutations(graphene.ObjectType):
    payment_capture = PaymentCapture.Field()
    payment_refund = PaymentRefund.Field()
    payment_void = PaymentVoid.Field()
    payment_initialize = PaymentInitialize.Field()
    payment_check_balance = PaymentCheckBalance.Field()

    transaction_create = TransactionCreate.Field()
    transaction_update = TransactionUpdate.Field()
    transaction_request_action = TransactionRequestAction.Field()
