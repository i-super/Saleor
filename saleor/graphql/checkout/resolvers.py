from ...checkout import models
from ...core.permissions import CheckoutPermissions
from ...core.tracing import traced_resolver
from ..utils import get_user_or_app_from_context


def resolve_checkout_lines():
    queryset = models.CheckoutLine.objects.all()
    return queryset


def resolve_checkouts(channel_slug):
    queryset = models.Checkout.objects.all()
    if channel_slug:
        queryset = queryset.filter(channel__slug=channel_slug)
    return queryset


@traced_resolver
def resolve_checkout(info, token):
    checkout = models.Checkout.objects.filter(token=token).first()

    if checkout is None:
        return None

    # resolve checkout in active channel
    if checkout.channel.is_active:
        # resolve checkout for anonymous customer
        if not checkout.user:
            return checkout

        # resolve checkout for logged-in customer
        if checkout.user == info.context.user:
            return checkout

    # resolve checkout for staff user
    requester = get_user_or_app_from_context(info.context)
    if requester.has_perm(CheckoutPermissions.MANAGE_CHECKOUTS):
        return checkout

    return None
