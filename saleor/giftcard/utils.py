from datetime import date
from typing import TYPE_CHECKING, Dict, Iterable, Optional

from dateutil.relativedelta import relativedelta
from django.db.models.expressions import Exists, OuterRef
from django.utils import timezone

from ..checkout.models import Checkout
from ..core.utils.promo_code import InvalidPromoCode, generate_promo_code
from ..core.utils.validators import user_is_valid
from ..order.models import OrderLine
from ..product import ProductTypeKind
from ..product.models import Product, ProductType, ProductVariant
from ..site import GiftCardSettingsExpiryType
from . import events
from .models import GiftCard
from .notifications import send_gift_card_notification

if TYPE_CHECKING:
    from ..account.models import User
    from ..app.models import App
    from ..order.models import Order
    from ..plugins.manager import PluginsManager
    from ..site.models import SiteSettings


def add_gift_card_code_to_checkout(
    checkout: Checkout, email: str, promo_code: str, currency: str
):
    """Add gift card data to checkout by code.

    Raise InvalidPromoCode if gift card cannot be applied.
    """
    try:
        # only active gift card with currency the same as channel currency can be used
        gift_card = (
            GiftCard.objects.active(date=date.today())
            .filter(currency=currency)
            .get(code=promo_code)
        )
    except GiftCard.DoesNotExist:
        raise InvalidPromoCode()

    used_by_email = gift_card.used_by_email
    # gift card can be used only by one user
    if used_by_email and used_by_email != email:
        raise InvalidPromoCode()

    checkout.gift_cards.add(gift_card)


def remove_gift_card_code_from_checkout(checkout: Checkout, gift_card_code: str):
    """Remove gift card data from checkout by code."""
    gift_card = checkout.gift_cards.filter(code=gift_card_code).first()
    if gift_card:
        checkout.gift_cards.remove(gift_card)


def deactivate_gift_card(gift_card: GiftCard):
    """Set gift card status as inactive."""
    if gift_card.is_active:
        gift_card.is_active = False
        gift_card.save(update_fields=["is_active"])


def activate_gift_card(gift_card: GiftCard):
    """Set gift card status as active."""
    if not gift_card.is_active:
        gift_card.is_active = True
        gift_card.save(update_fields=["is_active"])


def create_non_shippable_gift_cards(
    order: "Order",
    order_lines: Iterable[OrderLine],
    settings: "SiteSettings",
    requestor_user: Optional["User"],
    app: Optional["App"],
    manager: "PluginsManager",
):
    if not user_is_valid(requestor_user):
        requestor_user = None
    line_pks = [line.pk for line in order_lines]
    gift_card_lines = get_non_shippable_gift_card_lines(line_pks)
    if not gift_card_lines:
        return
    quantities = {line.pk: line.quantity for line in gift_card_lines}
    return gift_cards_create(
        order, gift_card_lines, quantities, settings, requestor_user, app, manager
    )


def get_non_shippable_gift_card_lines(line_ids: Iterable[int]):
    gift_card_lines = get_gift_card_lines(line_ids)
    gift_card_lines = gift_card_lines.filter(
        is_shipping_required=False,
    )
    return gift_card_lines


def get_gift_card_lines(line_pks: Iterable[int]):
    product_types = ProductType.objects.filter(kind=ProductTypeKind.GIFT_CARD)
    products = Product.objects.filter(
        Exists(product_types.filter(pk=OuterRef("product_type_id")))
    )
    variants = ProductVariant.objects.filter(
        Exists(products.filter(pk=OuterRef("product_id")))
    )
    gift_card_lines = OrderLine.objects.filter(id__in=line_pks).filter(
        Exists(variants.filter(pk=OuterRef("variant_id")))
    )

    return gift_card_lines


def gift_cards_create(
    order: "Order",
    gift_card_lines: Iterable["OrderLine"],
    quantities: Dict[int, int],
    settings: "SiteSettings",
    requestor_user: Optional["User"],
    app: Optional["App"],
    manager: "PluginsManager",
):
    """Create purchased gift cards."""
    customer_user = order.user
    user_email = order.user_email
    gift_cards = []
    non_shippable_gift_cards = []
    expiry_date = calculate_expiry_date(settings)
    for order_line in gift_card_lines:
        price = order_line.unit_price_gross
        line_gift_cards = [
            GiftCard(  # type: ignore
                code=generate_promo_code(),
                initial_balance=price,
                current_balance=price,
                created_by=customer_user,
                created_by_email=user_email,
                product=order_line.variant.product if order_line.variant else None,
                expiry_date=expiry_date,
            )
            for _ in range(quantities[order_line.pk])
        ]
        gift_cards.extend(line_gift_cards)
        if not order_line.is_shipping_required:
            non_shippable_gift_cards.extend(line_gift_cards)

    gift_cards = GiftCard.objects.bulk_create(gift_cards)
    events.gift_cards_bought(gift_cards, order.id, requestor_user, app)

    # send to customer all non-shippable gift cards
    send_gift_cards_to_customer(
        non_shippable_gift_cards, user_email, requestor_user, app, manager
    )
    return gift_cards


def calculate_expiry_date(settings):
    """Calculate expiry date based on gift card settings."""
    today = timezone.now().date()
    expiry_date = None
    if settings.gift_card_expiry_type == GiftCardSettingsExpiryType.EXPIRY_PERIOD:
        expiry_period_type = settings.gift_card_expiry_period_type
        time_delta = {f"{expiry_period_type}s": settings.gift_card_expiry_period}
        expiry_date = today + relativedelta(**time_delta)  # type: ignore
    return expiry_date


def send_gift_cards_to_customer(
    gift_cards: Iterable[GiftCard],
    user_email: str,
    requestor_user: Optional["User"],
    app: Optional["App"],
    manager: "PluginsManager",
):
    for gift_card in gift_cards:
        send_gift_card_notification(requestor_user, app, user_email, gift_card, manager)

    events.gift_cards_sent(gift_cards, requestor_user, app, user_email)
