import graphene

from ..core.fields import PrefetchingConnectionField
from ..decorators import permission_required
from .enums import PaymentGatewayEnum
from .mutations import PaymentCapture, PaymentRefund, PaymentSecureConfirm, PaymentVoid
from .resolvers import resolve_payments, resolve_client_token
from .types import Payment


class PaymentQueries(graphene.ObjectType):
    payment = graphene.Field(Payment, id=graphene.Argument(graphene.ID))
    payments = PrefetchingConnectionField(Payment, description="List of payments")
    payment_client_token = graphene.Field(
        graphene.String, args={"gateway": PaymentGatewayEnum()}
    )

    @permission_required("order.manage_orders")
    def resolve_payment(self, info, **data):
        return graphene.Node.get_node_from_global_id(info, data.get("id"), Payment)

    @permission_required("order.manage_orders")
    def resolve_payments(self, info, query=None, **_kwargs):
        return resolve_payments(info, query)

    def resolve_payment_client_token(self, info, gateway, **_kwargs):
        return resolve_client_token(info.context.user, gateway)


class PaymentMutations(graphene.ObjectType):
    payment_capture = PaymentCapture.Field()
    payment_refund = PaymentRefund.Field()
    payment_void = PaymentVoid.Field()
    payment_secure_confirm = PaymentSecureConfirm.Field()
