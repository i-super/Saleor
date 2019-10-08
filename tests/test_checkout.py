import datetime
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from django.utils import timezone
from django_countries.fields import Country
from freezegun import freeze_time
from prices import Money, TaxedMoney, TaxedMoneyRange

from saleor.account import CustomerEvents
from saleor.account.models import Address, CustomerEvent, User
from saleor.account.utils import store_user_address
from saleor.checkout import AddressType, views
from saleor.checkout.forms import CheckoutVoucherForm, CountryForm
from saleor.checkout.utils import (
    add_variant_to_checkout,
    add_voucher_to_checkout,
    change_billing_address_in_checkout,
    change_shipping_address_in_checkout,
    clear_shipping_method,
    create_order,
    get_checkout_context,
    get_shipping_price_estimate,
    get_voucher_discount_for_checkout,
    get_voucher_for_checkout,
    is_valid_shipping_method,
    prepare_order_data,
    recalculate_checkout_discount,
    remove_voucher_from_checkout,
)
from saleor.core.exceptions import InsufficientStock
from saleor.core.taxes import zero_money, zero_taxed_money
from saleor.discount import DiscountValueType, VoucherType
from saleor.discount.models import NotApplicable, Voucher
from saleor.extensions.manager import ExtensionsManager, get_extensions_manager
from saleor.order import OrderEvents, OrderEventsEmails
from saleor.order.models import OrderEvent
from saleor.shipping.models import ShippingZone

from .utils import get_redirect_location


def test_country_form_country_choices():
    form = CountryForm(data={"csrf": "", "country": "PL"})
    assert form.fields["country"].choices == []

    zone = ShippingZone.objects.create(countries=["PL", "DE"], name="Europe")
    form = CountryForm(data={"csrf": "", "country": "PL"})

    expected_choices = [(country.code, country.name) for country in zone.countries]
    expected_choices = sorted(expected_choices, key=lambda choice: choice[1])
    assert form.fields["country"].choices == expected_choices


def test_is_valid_shipping_method(checkout_with_item, address, shipping_zone):
    checkout = checkout_with_item
    checkout.shipping_address = address
    checkout.save()
    # no shipping method assigned
    assert not is_valid_shipping_method(checkout, None)
    shipping_method = shipping_zone.shipping_methods.first()
    checkout.shipping_method = shipping_method
    checkout.save()

    assert is_valid_shipping_method(checkout, None)

    zone = ShippingZone.objects.create(name="DE", countries=["DE"])
    shipping_method.shipping_zone = zone
    shipping_method.save()
    assert not is_valid_shipping_method(checkout, None)


def test_clear_shipping_method(checkout, shipping_method):
    checkout.shipping_method = shipping_method
    checkout.save()
    clear_shipping_method(checkout)
    checkout.refresh_from_db()
    assert not checkout.shipping_method


@pytest.mark.parametrize(
    "checkout_length, is_shipping_required, redirect_url",
    [
        (0, True, reverse("checkout:index")),
        (0, False, reverse("checkout:index")),
        (1, True, reverse("checkout:shipping-address")),
        (1, False, reverse("checkout:summary")),
    ],
)
def test_view_checkout_index(
    monkeypatch, rf, checkout_length, is_shipping_required, redirect_url
):
    checkout = Mock(
        __len__=Mock(return_value=checkout_length),
        is_shipping_required=Mock(return_value=is_shipping_required),
    )
    monkeypatch.setattr(
        "saleor.checkout.utils.get_checkout_from_request", lambda req, qs: checkout
    )
    url = reverse("checkout:start")
    request = rf.get(url, follow=True)

    response = views.checkout_start(request)

    assert response.url == redirect_url


def test_view_checkout_index_authorized_user(
    authorized_client, customer_user, request_checkout_with_item
):
    request_checkout_with_item.user = customer_user
    request_checkout_with_item.save()
    url = reverse("checkout:start")

    response = authorized_client.get(url, follow=True)

    redirect_url = reverse("checkout:shipping-address")
    assert response.request["PATH_INFO"] == redirect_url


def test_view_checkout_shipping_address(client, request_checkout_with_item):
    url = reverse("checkout:shipping-address")
    data = {
        "email": "test@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "street_address_1": "Aleje Jerozolimskie 2",
        "street_address_2": "",
        "city": "Warszawa",
        "city_area": "",
        "country_area": "",
        "postal_code": "00-374",
        "phone": "+48536984008",
        "country": "PL",
    }

    response = client.get(url)

    assert response.request["PATH_INFO"] == url

    response = client.post(url, data, follow=True)

    redirect_url = reverse("checkout:shipping-method")
    assert response.request["PATH_INFO"] == redirect_url
    assert request_checkout_with_item.email == "test@example.com"


def test_view_checkout_shipping_address_with_invalid_data(
    client, request_checkout_with_item
):
    url = reverse("checkout:shipping-address")
    data = {
        "email": "test@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "street_address_1": "Aleje Jerozolimskie 2",
        "street_address_2": "",
        "city": "Warszawa",
        "city_area": "",
        "country_area": "",
        "postal_code": "00-37412",
        "phone": "+48536984008",
        "country": "PL",
    }

    response = client.post(url, data, follow=True)
    assert response.request["PATH_INFO"] == url


def test_view_checkout_shipping_address_authorized_user(
    authorized_client, customer_user, request_checkout_with_item
):
    request_checkout_with_item.user = customer_user
    request_checkout_with_item.save()
    url = reverse("checkout:shipping-address")
    data = {"address": customer_user.default_billing_address.pk}

    response = authorized_client.post(url, data, follow=True)

    redirect_url = reverse("checkout:shipping-method")
    assert response.request["PATH_INFO"] == redirect_url
    assert request_checkout_with_item.email == customer_user.email


def test_view_checkout_shipping_address_without_shipping(
    request_checkout, product_without_shipping, client
):
    variant = product_without_shipping.variants.get()
    add_variant_to_checkout(request_checkout, variant)
    url = reverse("checkout:shipping-address")

    response = client.get(url)

    assert response.status_code == 302
    assert get_redirect_location(response) == reverse("checkout:summary")
    assert not request_checkout.email


def test_view_checkout_shipping_method(
    client, shipping_zone, address, request_checkout_with_item
):
    request_checkout_with_item.shipping_address = address
    request_checkout_with_item.email = "test@example.com"
    request_checkout_with_item.save()
    url = reverse("checkout:shipping-method")
    data = {"shipping_method": shipping_zone.shipping_methods.first().pk}

    response = client.get(url)

    assert response.request["PATH_INFO"] == url

    response = client.post(url, data, follow=True)

    redirect_url = reverse("checkout:summary")
    assert response.request["PATH_INFO"] == redirect_url


def test_view_checkout_shipping_method_authorized_user(
    authorized_client, customer_user, shipping_zone, address, request_checkout_with_item
):
    request_checkout_with_item.user = customer_user
    request_checkout_with_item.email = customer_user.email
    request_checkout_with_item.shipping_address = address
    request_checkout_with_item.save()
    url = reverse("checkout:shipping-method")
    data = {"shipping_method": shipping_zone.shipping_methods.first().pk}

    response = authorized_client.get(url)

    assert response.request["PATH_INFO"] == url

    response = authorized_client.post(url, data, follow=True)

    redirect_url = reverse("checkout:summary")
    assert response.request["PATH_INFO"] == redirect_url


def test_view_checkout_shipping_method_without_shipping(
    request_checkout, product_without_shipping, client
):
    variant = product_without_shipping.variants.get()
    add_variant_to_checkout(request_checkout, variant)
    url = reverse("checkout:shipping-method")

    response = client.get(url)

    assert response.status_code == 302
    assert get_redirect_location(response) == reverse("checkout:summary")


def test_view_checkout_shipping_method_without_address(
    request_checkout_with_item, client
):
    url = reverse("checkout:shipping-method")

    response = client.get(url)

    assert response.status_code == 302
    redirect_url = reverse("checkout:shipping-address")
    assert get_redirect_location(response) == redirect_url


@patch("saleor.checkout.utils.send_order_confirmation")
def test_view_checkout_summary_finalize_with_voucher(
    mock_send_confirmation,
    client,
    shipping_zone,
    address,
    request_checkout_with_item,
    voucher,
):
    checkout = request_checkout_with_item
    expected_voucher_usage_count = voucher.used + 1

    checkout.shipping_address = address
    checkout.voucher_code = voucher.code
    checkout.email = "test@example.com"
    checkout.shipping_method = shipping_zone.shipping_methods.first()
    checkout.save()

    url = reverse("checkout:summary")
    data = {"address": "shipping_address"}

    response = client.get(url)
    assert response.status_code == 200
    assert response.request["PATH_INFO"] == url

    response = client.post(url, data, follow=True)
    assert response.status_code == 200

    order = response.context["order"]
    assert order.user_email == "test@example.com"
    redirect_url = reverse("order:payment", kwargs={"token": order.token})
    assert response.request["PATH_INFO"] == redirect_url

    # we expect the user to be anonymous, thus None
    mock_send_confirmation.delay.assert_called_once_with(order.pk, None)

    # checkout should be deleted after order is created
    assert checkout.pk is None

    # Ensure the voucher was updated
    voucher.refresh_from_db(fields=["used"])
    assert voucher.used == expected_voucher_usage_count


@patch("saleor.checkout.utils.send_order_confirmation")
def test_view_checkout_summary_anonymous_user(
    mock_send_confirmation, client, shipping_zone, address, request_checkout_with_item
):
    request_checkout_with_item.shipping_address = address
    request_checkout_with_item.email = "test@example.com"
    request_checkout_with_item.shipping_method = shipping_zone.shipping_methods.first()
    request_checkout_with_item.save()
    url = reverse("checkout:summary")
    data = {"address": "shipping_address"}

    response = client.get(url)

    assert response.request["PATH_INFO"] == url

    response = client.post(url, data, follow=True)

    order = response.context["order"]
    assert order.user_email == "test@example.com"
    redirect_url = reverse("order:payment", kwargs={"token": order.token})
    assert response.request["PATH_INFO"] == redirect_url

    # we expect the user to be anonymous, thus None
    mock_send_confirmation.delay.assert_called_once_with(order.pk, None)

    # checkout should be deleted after order is created
    assert request_checkout_with_item.pk is None


@patch("saleor.checkout.utils.send_order_confirmation")
def test_view_checkout_summary_authorized_user(
    mock_send_confirmation,
    authorized_client,
    customer_user,
    shipping_zone,
    address,
    request_checkout_with_item,
):
    request_checkout_with_item.shipping_address = address
    request_checkout_with_item.user = customer_user
    request_checkout_with_item.email = customer_user.email
    request_checkout_with_item.shipping_method = shipping_zone.shipping_methods.first()
    request_checkout_with_item.save()
    url = reverse("checkout:summary")
    data = {"address": "shipping_address"}

    response = authorized_client.get(url)

    assert response.request["PATH_INFO"] == url

    response = authorized_client.post(url, data, follow=True)

    order = response.context["order"]
    assert order.user_email == customer_user.email
    redirect_url = reverse("order:payment", kwargs={"token": order.token})
    assert response.request["PATH_INFO"] == redirect_url
    mock_send_confirmation.delay.assert_called_once_with(order.pk, customer_user.pk)


@patch("saleor.checkout.utils.send_order_confirmation")
def test_view_checkout_summary_save_language(
    mock_send_confirmation,
    authorized_client,
    customer_user,
    shipping_zone,
    address,
    request_checkout_with_item,
    settings,
):
    settings.LANGUAGE_CODE = "en"
    user_language = "fr"
    authorized_client.cookies[settings.LANGUAGE_COOKIE_NAME] = user_language
    url = reverse("set_language")
    data = {"language": "fr"}

    authorized_client.post(url, data)

    request_checkout_with_item.shipping_address = address
    request_checkout_with_item.user = customer_user
    request_checkout_with_item.email = customer_user.email
    request_checkout_with_item.shipping_method = shipping_zone.shipping_methods.first()
    request_checkout_with_item.save()
    url = reverse("checkout:summary")
    data = {"address": "shipping_address"}

    response = authorized_client.get(url, HTTP_ACCEPT_LANGUAGE=user_language)

    assert response.request["PATH_INFO"] == url

    response = authorized_client.post(
        url, data, follow=True, HTTP_ACCEPT_LANGUAGE=user_language
    )

    order = response.context["order"]
    assert order.user_email == customer_user.email
    assert order.language_code == user_language
    redirect_url = reverse("order:payment", kwargs={"token": order.token})
    assert response.request["PATH_INFO"] == redirect_url
    mock_send_confirmation.delay.assert_called_once_with(order.pk, customer_user.pk)


def test_view_checkout_summary_without_address(request_checkout_with_item, client):
    url = reverse("checkout:summary")

    response = client.get(url)

    assert response.status_code == 302
    redirect_url = reverse("checkout:shipping-address")
    assert get_redirect_location(response) == redirect_url


def test_view_checkout_summary_without_shipping_zone(
    request_checkout_with_item, client, address
):
    request_checkout_with_item.shipping_address = address
    request_checkout_with_item.email = "test@example.com"
    request_checkout_with_item.save()

    url = reverse("checkout:summary")
    response = client.get(url)

    assert response.status_code == 302
    redirect_url = reverse("checkout:shipping-method")
    assert get_redirect_location(response) == redirect_url


def test_view_checkout_summary_with_invalid_voucher(
    client, request_checkout_with_item, shipping_zone, address, voucher
):
    voucher.usage_limit = 3
    voucher.save()

    request_checkout_with_item.shipping_address = address
    request_checkout_with_item.email = "test@example.com"
    request_checkout_with_item.shipping_method = shipping_zone.shipping_methods.first()
    request_checkout_with_item.save()

    url = reverse("checkout:summary")
    voucher_url = "{url}?next={url}".format(url=url)
    data = {"discount-voucher": voucher.code}

    response = client.post(voucher_url, data, follow=True, HTTP_REFERER=url)

    assert response.context["checkout"].voucher_code == voucher.code

    voucher.used = 3
    voucher.save()

    data = {"address": "shipping_address"}
    response = client.post(url, data, follow=True)
    checkout = response.context["checkout"]
    assert not checkout.voucher_code
    assert not checkout.discount_amount
    assert not checkout.discount_name

    response = client.post(url, data, follow=True)
    order = response.context["order"]
    assert not order.voucher
    assert not order.discount_amount
    assert not order.discount_name


def test_view_checkout_summary_with_invalid_voucher_code(
    client, request_checkout_with_item, shipping_zone, address
):
    request_checkout_with_item.shipping_address = address
    request_checkout_with_item.email = "test@example.com"
    request_checkout_with_item.shipping_method = shipping_zone.shipping_methods.first()
    request_checkout_with_item.save()

    url = reverse("checkout:summary")
    voucher_url = "{url}?next={url}".format(url=url)
    data = {"discount-voucher": "invalid-code"}

    response = client.post(voucher_url, data, follow=True, HTTP_REFERER=url)

    assert "voucher" in response.context["voucher_form"].errors
    assert response.context["checkout"].voucher_code is None


def test_view_checkout_place_order_with_expired_voucher_code(
    client, request_checkout_with_item, shipping_zone, address, voucher
):

    checkout = request_checkout_with_item

    # add shipping information to the checkout
    checkout.shipping_address = address
    checkout.email = "test@example.com"
    checkout.shipping_method = shipping_zone.shipping_methods.first()

    # set voucher to be expired
    yesterday = timezone.now() - datetime.timedelta(days=1)
    voucher.end_date = yesterday
    voucher.save()

    # put the voucher code to checkout
    checkout.voucher_code = voucher.code

    # save the checkout
    checkout.save()

    checkout_url = reverse("checkout:summary")

    # place order
    data = {"address": "shipping_address"}
    response = client.post(checkout_url, data, follow=True)

    # order should not have been placed
    assert response.request["PATH_INFO"] == checkout_url

    # ensure the voucher was removed
    checkout.refresh_from_db()
    assert not checkout.voucher_code


def test_view_checkout_place_order_with_item_out_of_stock(
    client, request_checkout_with_item, shipping_zone, address, voucher, product
):

    checkout = request_checkout_with_item
    variant = product.variants.get()

    # add shipping information to the checkout
    checkout.shipping_address = address
    checkout.email = "test@example.com"
    checkout.shipping_method = shipping_zone.shipping_methods.first()
    checkout.save()

    # make the variant be out of stock
    variant.quantity = 0
    variant.save()

    checkout_url = reverse("checkout:summary")
    redirect_url = reverse("checkout:index")

    # place order
    data = {"address": "shipping_address"}
    response = client.post(checkout_url, data, follow=True)

    # order should have been aborted,
    # and user should have been redirected to its checkout
    assert response.request["PATH_INFO"] == redirect_url


def test_view_checkout_place_order_without_shipping_address(
    client, request_checkout_with_item, shipping_zone
):

    checkout = request_checkout_with_item

    # add shipping information to the checkout
    checkout.email = "test@example.com"
    checkout.shipping_method = shipping_zone.shipping_methods.first()

    # save the checkout
    checkout.save()

    checkout_url = reverse("checkout:summary")
    redirect_url = reverse("checkout:shipping-address")

    # place order
    data = {"address": "shipping_address"}
    response = client.post(checkout_url, data, follow=True)

    # order should have been aborted,
    # and user should have been redirected to its checkout
    assert response.request["PATH_INFO"] == redirect_url


def test_view_checkout_summary_remove_voucher(
    client, request_checkout_with_item, shipping_zone, voucher, address
):
    request_checkout_with_item.shipping_address = address
    request_checkout_with_item.email = "test@example.com"
    request_checkout_with_item.shipping_method = shipping_zone.shipping_methods.first()
    request_checkout_with_item.save()

    remove_voucher_url = reverse("checkout:summary")
    voucher_url = "{url}?next={url}".format(url=remove_voucher_url)
    data = {"discount-voucher": voucher.code}

    response = client.post(
        voucher_url, data, follow=True, HTTP_REFERER=remove_voucher_url
    )

    assert response.context["checkout"].voucher_code == voucher.code

    url = reverse("checkout:remove-voucher")

    response = client.post(url, follow=True, HTTP_REFERER=remove_voucher_url)

    assert not response.context["checkout"].voucher_code


@pytest.mark.parametrize("is_anonymous_user", (True, False))
def test_create_order_creates_expected_events(
    request_checkout_with_item, customer_user, shipping_method, is_anonymous_user
):
    checkout = request_checkout_with_item
    checkout_user = None if is_anonymous_user else customer_user

    # Ensure not events are existing prior
    assert not OrderEvent.objects.exists()
    assert not CustomerEvent.objects.exists()

    # Prepare valid checkout
    checkout.user = checkout_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_shipping_address
    checkout.shipping_method = shipping_method
    checkout.save()

    # Place checkout
    order = create_order(
        checkout=checkout,
        order_data=prepare_order_data(
            checkout=checkout, tracking_code="tracking_code", discounts=None
        ),
        user=customer_user if not is_anonymous_user else AnonymousUser(),
    )

    # Ensure only two events were created, and retrieve them
    placement_event, email_sent_event = order.events.all()  # type: OrderEvent

    # Ensure the correct order event was created
    assert placement_event.type == OrderEvents.PLACED  # is the event the expected type
    assert placement_event.user == checkout_user  # is the user anonymous/ the customer
    assert placement_event.order is order  # is the associated backref order valid
    assert placement_event.date  # ensure a date was set
    assert not placement_event.parameters  # should not have any additional parameters

    # Ensure the correct email sent event was created
    assert email_sent_event.type == OrderEvents.EMAIL_SENT  # should be email sent event
    assert email_sent_event.user == checkout_user  # ensure the user is none or valid
    assert email_sent_event.order is order  # ensure the mail event is related to order
    assert email_sent_event.date  # ensure a date was set
    assert email_sent_event.parameters == {  # ensure the correct parameters were set
        "email": order.get_customer_email(),
        "email_type": OrderEventsEmails.ORDER,
    }

    # Check no event was created if the user was anonymous
    if is_anonymous_user:
        assert not CustomerEvent.objects.exists()  # should not have created any event
        return  # we are done testing as the user is anonymous

    # Ensure the correct customer event was created if the user was not anonymous
    placement_event = customer_user.events.get()  # type: CustomerEvent
    assert placement_event.type == CustomerEvents.PLACED_ORDER  # check the event type
    assert placement_event.user == customer_user  # check the backref is valid
    assert placement_event.order == order  # check the associated order is valid
    assert placement_event.date  # ensure a date was set
    assert not placement_event.parameters  # should not have any additional parameters


def test_create_order_insufficient_stock(
    request_checkout, customer_user, product_without_shipping
):
    variant = product_without_shipping.variants.get()
    add_variant_to_checkout(request_checkout, variant, 10, check_quantity=False)
    request_checkout.user = customer_user
    request_checkout.billing_address = customer_user.default_billing_address
    request_checkout.shipping_address = customer_user.default_billing_address
    request_checkout.save()

    with pytest.raises(InsufficientStock):
        prepare_order_data(
            checkout=request_checkout, tracking_code="tracking_code", discounts=None
        )


def test_create_order_doesnt_duplicate_order(
    checkout_with_item, customer_user, shipping_method
):
    checkout = checkout_with_item
    checkout.user = customer_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_billing_address
    checkout.shipping_method = shipping_method
    checkout.save()

    order_data = prepare_order_data(checkout=checkout, tracking_code="", discounts=None)

    order_1 = create_order(checkout=checkout, order_data=order_data, user=customer_user)
    assert order_1.checkout_token == checkout.token

    order_2 = create_order(checkout=checkout, order_data=order_data, user=customer_user)
    assert order_1.pk == order_2.pk


@pytest.mark.parametrize("is_anonymous_user", (True, False))
def test_create_order_with_gift_card(
    checkout_with_gift_card, customer_user, shipping_method, is_anonymous_user
):
    checkout_user = None if is_anonymous_user else customer_user
    checkout = checkout_with_gift_card
    checkout.user = checkout_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_billing_address
    checkout.shipping_method = shipping_method
    checkout.save()

    subtotal = checkout.get_subtotal()
    shipping_price = checkout.get_shipping_price()
    total_gross_without_gift_cards = (
        TaxedMoney(subtotal, subtotal)
        + TaxedMoney(shipping_price, shipping_price)
        - checkout.discount
    ).gross
    gift_cards_balance = checkout.get_total_gift_cards_balance()

    order = create_order(
        checkout=checkout,
        order_data=prepare_order_data(
            checkout=checkout, tracking_code="tracking_code", discounts=None
        ),
        user=customer_user if not is_anonymous_user else AnonymousUser(),
    )

    assert order.gift_cards.count() == 1
    assert order.gift_cards.first().current_balance.amount == 0
    assert order.total.gross == (total_gross_without_gift_cards - gift_cards_balance)


def test_create_order_with_gift_card_partial_use(
    checkout_with_item, gift_card_used, customer_user, shipping_method
):
    checkout = checkout_with_item
    checkout.user = customer_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_billing_address
    checkout.shipping_method = shipping_method
    checkout.save()

    checkout_total = checkout.get_total()
    price_without_gift_card = TaxedMoney(net=checkout_total, gross=checkout_total)
    gift_card_balance_before_order = gift_card_used.current_balance_amount

    checkout.gift_cards.add(gift_card_used)
    checkout.save()

    order = create_order(
        checkout=checkout,
        order_data=prepare_order_data(
            checkout=checkout, tracking_code="tracking_code", discounts=None
        ),
        user=customer_user,
    )

    gift_card_used.refresh_from_db()

    expected_old_balance = (
        price_without_gift_card.gross.amount + gift_card_used.current_balance_amount
    )

    assert order.gift_cards.count() > 0
    assert order.total == zero_taxed_money()
    assert gift_card_balance_before_order == expected_old_balance


def test_create_order_with_many_gift_cards(
    checkout_with_item,
    gift_card_created_by_staff,
    gift_card,
    customer_user,
    shipping_method,
):
    checkout = checkout_with_item
    checkout.user = customer_user
    checkout.billing_address = customer_user.default_billing_address
    checkout.shipping_address = customer_user.default_billing_address
    checkout.shipping_method = shipping_method
    checkout.save()

    checkout_total = checkout.get_total()
    price_without_gift_card = TaxedMoney(net=checkout_total, gross=checkout_total)
    gift_cards_balance_before_order = (
        gift_card_created_by_staff.current_balance.amount
        + gift_card.current_balance.amount
    )

    checkout.gift_cards.add(gift_card_created_by_staff)
    checkout.gift_cards.add(gift_card)
    checkout.save()

    order = create_order(
        checkout=checkout,
        order_data=prepare_order_data(
            checkout=checkout, tracking_code="tracking_code", discounts=None
        ),
        user=customer_user,
    )

    gift_card_created_by_staff.refresh_from_db()
    gift_card.refresh_from_db()
    zero_price = zero_money()
    assert order.gift_cards.count() > 0
    assert gift_card_created_by_staff.current_balance == zero_price
    assert gift_card.current_balance == zero_price
    assert price_without_gift_card.gross.amount == (
        gift_cards_balance_before_order + order.total.gross.amount
    )


def test_note_in_created_order(request_checkout_with_item, address, customer_user):
    request_checkout_with_item.shipping_address = address
    request_checkout_with_item.note = "test_note"
    request_checkout_with_item.save()
    order = create_order(
        checkout=request_checkout_with_item,
        order_data=prepare_order_data(
            checkout=request_checkout_with_item,
            tracking_code="tracking_code",
            discounts=None,
        ),
        user=customer_user,
    )
    assert order.customer_note == request_checkout_with_item.note


@pytest.mark.parametrize(
    "total, min_spent_amount, total_quantity, min_checkout_items_quantity, "
    "discount_value, discount_value_type, expected_value",
    [
        (20, 20, 2, 2, 50, DiscountValueType.PERCENTAGE, 10),
        (20, None, 2, None, 50, DiscountValueType.PERCENTAGE, 10),
        (20, 20, 2, 2, 5, DiscountValueType.FIXED, 5),
        (20, None, 2, None, 5, DiscountValueType.FIXED, 5),
    ],
)
def test_get_discount_for_checkout_value_voucher(
    total,
    min_spent_amount,
    total_quantity,
    min_checkout_items_quantity,
    discount_value,
    discount_value_type,
    expected_value,
):
    voucher = Voucher(
        code="unique",
        type=VoucherType.ENTIRE_ORDER,
        discount_value_type=discount_value_type,
        discount_value=discount_value,
        min_spent=(
            Money(min_spent_amount, "USD") if min_spent_amount is not None else None
        ),
        min_checkout_items_quantity=min_checkout_items_quantity,
    )
    checkout = Mock(
        get_subtotal=Mock(return_value=Money(total, "USD")), quantity=total_quantity
    )
    discount = get_voucher_discount_for_checkout(voucher, checkout)
    assert discount == Money(expected_value, "USD")


@patch("saleor.discount.utils.validate_voucher")
def test_get_voucher_discount_for_checkout_voucher_validation(
    mock_validate_voucher, voucher, checkout_with_voucher
):
    get_voucher_discount_for_checkout(voucher, checkout_with_voucher)
    manager = get_extensions_manager()
    subtotal = manager.calculate_checkout_subtotal(checkout_with_voucher, [])
    quantity = checkout_with_voucher.quantity
    customer_email = checkout_with_voucher.get_customer_email()
    mock_validate_voucher.assert_called_once_with(
        voucher, subtotal.gross, quantity, customer_email
    )


@pytest.mark.parametrize(
    "total, total_quantity, discount_value, discount_type, min_spent_amount, "
    "min_checkout_items_quantity",
    [
        ("99", 9, 10, DiscountValueType.FIXED, None, 10),
        ("99", 9, 10, DiscountValueType.FIXED, 100, None),
        ("99", 10, 10, DiscountValueType.PERCENTAGE, 100, 10),
        ("100", 9, 10, DiscountValueType.PERCENTAGE, 100, 10),
        ("99", 9, 10, DiscountValueType.PERCENTAGE, 100, 10),
    ],
)
def test_get_discount_for_checkout_entire_order_voucher_not_applicable(
    total,
    total_quantity,
    discount_value,
    discount_type,
    min_spent_amount,
    min_checkout_items_quantity,
):
    voucher = Voucher(
        code="unique",
        type=VoucherType.ENTIRE_ORDER,
        discount_value_type=discount_type,
        discount_value=discount_value,
        min_spent=(
            Money(min_spent_amount, "USD") if min_spent_amount is not None else None
        ),
        min_checkout_items_quantity=min_checkout_items_quantity,
    )
    checkout = Mock(
        get_subtotal=Mock(return_value=Money(total, "USD")), quantity=total_quantity
    )
    with pytest.raises(NotApplicable):
        get_voucher_discount_for_checkout(voucher, checkout)


@pytest.mark.parametrize(
    "discount_value, discount_type, apply_once_per_order, discount_amount",
    [
        (5, DiscountValueType.FIXED, True, 5),
        (5, DiscountValueType.FIXED, False, 15),
        (10000, DiscountValueType.FIXED, True, 10),
        (10, DiscountValueType.PERCENTAGE, True, 1),
        (10, DiscountValueType.PERCENTAGE, False, 5),
    ],
)
def test_get_discount_for_checkout_specific_products_voucher(
    checkout_with_items,
    product_list,
    discount_value,
    discount_type,
    apply_once_per_order,
    discount_amount,
):
    voucher = Voucher.objects.create(
        code="unique",
        type=VoucherType.SPECIFIC_PRODUCT,
        discount_value_type=discount_type,
        discount_value=discount_value,
        apply_once_per_order=apply_once_per_order,
    )
    for product in product_list:
        voucher.products.add(product)
    discount = get_voucher_discount_for_checkout(voucher, checkout_with_items)
    assert discount == Money(discount_amount, "USD")


@pytest.mark.parametrize(
    "total, total_quantity, discount_value, discount_type, min_spent_amount,"
    "min_checkout_items_quantity",
    [
        ("99", 9, 10, DiscountValueType.FIXED, None, 10),
        ("99", 9, 10, DiscountValueType.FIXED, 100, None),
        ("99", 10, 10, DiscountValueType.PERCENTAGE, 100, 10),
        ("100", 9, 10, DiscountValueType.PERCENTAGE, 100, 10),
        ("99", 9, 10, DiscountValueType.PERCENTAGE, 100, 10),
    ],
)
def test_get_discount_for_checkout_specific_products_voucher_not_applicable(
    monkeypatch,
    total,
    total_quantity,
    discount_value,
    discount_type,
    min_spent_amount,
    min_checkout_items_quantity,
):
    discounts = []
    monkeypatch.setattr(
        "saleor.checkout.utils.get_prices_of_discounted_specific_product",
        lambda checkout, discounts, product: [],
    )
    voucher = Voucher(
        code="unique",
        type=VoucherType.SPECIFIC_PRODUCT,
        discount_value_type=discount_type,
        discount_value=discount_value,
        min_spent=(
            Money(min_spent_amount, "USD") if min_spent_amount is not None else None
        ),
        min_checkout_items_quantity=min_checkout_items_quantity,
    )
    checkout = Mock(
        get_subtotal=Mock(return_value=Money(total, "USD")), quantity=total_quantity
    )
    with pytest.raises(NotApplicable):
        get_voucher_discount_for_checkout(voucher, checkout, discounts)


@pytest.mark.parametrize(
    "shipping_cost, shipping_country_code, discount_value, discount_type,"
    "countries, expected_value",
    [
        (10, None, 50, DiscountValueType.PERCENTAGE, [], 5),
        (10, None, 20, DiscountValueType.FIXED, [], 10),
        (10, "PL", 20, DiscountValueType.FIXED, [], 10),
        (5, "PL", 5, DiscountValueType.FIXED, ["PL"], 5),
    ],
)
def test_get_discount_for_checkout_shipping_voucher(
    shipping_cost,
    shipping_country_code,
    discount_value,
    discount_type,
    countries,
    expected_value,
):
    subtotal = Money(100, "USD")
    shipping_total = Money(shipping_cost, "USD")
    checkout = Mock(
        get_subtotal=Mock(return_value=subtotal),
        is_shipping_required=Mock(return_value=True),
        shipping_method=Mock(get_total=Mock(return_value=shipping_total)),
        get_shipping_price=Mock(return_value=shipping_total),
        shipping_address=Mock(country=Country(shipping_country_code)),
    )
    voucher = Voucher(
        code="unique",
        type=VoucherType.SHIPPING,
        discount_value_type=discount_type,
        discount_value=discount_value,
        countries=countries,
    )
    discount = get_voucher_discount_for_checkout(voucher, checkout)
    assert discount == Money(expected_value, "USD")


def test_get_discount_for_checkout_shipping_voucher_all_countries():
    subtotal = Money(100, "USD")
    shipping_total = Money(10, "USD")
    checkout = Mock(
        get_subtotal=Mock(return_value=subtotal),
        is_shipping_required=Mock(return_value=True),
        shipping_method=Mock(get_total=Mock(return_value=shipping_total)),
        get_shipping_price=Mock(return_value=shipping_total),
        shipping_address=Mock(country=Country("PL")),
    )
    voucher = Voucher(
        code="unique",
        type=VoucherType.SHIPPING,
        discount_value_type=DiscountValueType.PERCENTAGE,
        discount_value=50,
        countries=[],
    )

    discount = get_voucher_discount_for_checkout(voucher, checkout)

    assert discount == Money(5, "USD")


def test_get_discount_for_checkout_shipping_voucher_limited_countries(monkeypatch):
    subtotal = TaxedMoney(net=Money(100, "USD"), gross=Money(100, "USD"))
    shipping_total = TaxedMoney(net=Money(10, "USD"), gross=Money(10, "USD"))
    monkeypatch.setattr(
        ExtensionsManager, "calculate_checkout_subtotal", Mock(return_value=subtotal)
    )
    checkout = Mock(
        get_subtotal=Mock(return_value=subtotal),
        is_shipping_required=Mock(return_value=True),
        shipping_method=Mock(get_total=Mock(return_value=shipping_total)),
        shipping_address=Mock(country=Country("PL")),
    )
    voucher = Voucher(
        code="unique",
        type=VoucherType.SHIPPING,
        discount_value_type=DiscountValueType.PERCENTAGE,
        discount_value=50,
        countries=["UK", "DE"],
    )

    with pytest.raises(NotApplicable):
        get_voucher_discount_for_checkout(voucher, checkout)


@pytest.mark.parametrize(
    "is_shipping_required, shipping_method, discount_value, discount_type,"
    "countries, min_spent_amount, min_checkout_items_quantity, subtotal,"
    "total_quantity, error_msg",
    [
        (
            True,
            Mock(shipping_zone=Mock(countries=["PL"])),
            10,
            DiscountValueType.FIXED,
            ["US"],
            None,
            None,
            Money(10, "USD"),
            10,
            "This offer is not valid in your country.",
        ),
        (
            True,
            None,
            10,
            DiscountValueType.FIXED,
            [],
            None,
            None,
            Money(10, "USD"),
            10,
            "Please select a shipping method first.",
        ),
        (
            False,
            None,
            10,
            DiscountValueType.FIXED,
            [],
            None,
            None,
            Money(10, "USD"),
            10,
            "Your order does not require shipping.",
        ),
        (
            True,
            Mock(price=Money(10, "USD")),
            10,
            DiscountValueType.FIXED,
            [],
            5,
            None,
            Money(2, "USD"),
            10,
            "This offer is only valid for orders over $5.00.",
        ),
        (
            True,
            Mock(price=Money(10, "USD")),
            10,
            DiscountValueType.FIXED,
            [],
            5,
            10,
            Money(5, "USD"),
            9,
            "This offer is only valid for orders with a minimum of 10 quantity.",
        ),
        (
            True,
            Mock(price=Money(10, "USD")),
            10,
            DiscountValueType.FIXED,
            [],
            5,
            10,
            Money(2, "USD"),
            9,
            "This offer is only valid for orders over $5.00.",
        ),
    ],
)
def test_get_discount_for_checkout_shipping_voucher_not_applicable(
    is_shipping_required,
    shipping_method,
    discount_value,
    discount_type,
    countries,
    min_spent_amount,
    min_checkout_items_quantity,
    subtotal,
    total_quantity,
    error_msg,
):
    checkout = Mock(
        get_subtotal=Mock(return_value=subtotal),
        is_shipping_required=Mock(return_value=is_shipping_required),
        shipping_method=shipping_method,
        get_shipping_price=Mock(return_value=Money(10, "USD")),
        quantity=total_quantity,
    )
    voucher = Voucher(
        code="unique",
        type=VoucherType.SHIPPING,
        discount_value_type=discount_type,
        discount_value=discount_value,
        min_spent=(
            Money(min_spent_amount, "USD") if min_spent_amount is not None else None
        ),
        min_checkout_items_quantity=min_checkout_items_quantity,
        countries=countries,
    )
    with pytest.raises(NotApplicable) as e:
        get_voucher_discount_for_checkout(voucher, checkout)
    assert str(e.value) == error_msg


def test_checkout_voucher_form_invalid_voucher_code(
    monkeypatch, request_checkout_with_item
):
    form = CheckoutVoucherForm(
        {"voucher": "invalid"}, instance=request_checkout_with_item
    )
    assert not form.is_valid()
    assert "voucher" in form.errors


def test_checkout_voucher_form_voucher_not_applicable(
    voucher, request_checkout_with_item
):
    voucher.min_spent = Money(200, "USD")
    voucher.save()
    form = CheckoutVoucherForm(
        {"voucher": voucher.code}, instance=request_checkout_with_item
    )
    assert not form.is_valid()
    assert "voucher" in form.errors


def test_checkout_voucher_form_active_queryset_voucher_not_active(
    voucher, request_checkout_with_item
):
    assert Voucher.objects.count() == 1
    voucher.start_date = timezone.now() + datetime.timedelta(days=1)
    voucher.save()
    form = CheckoutVoucherForm(
        {"voucher": voucher.code}, instance=request_checkout_with_item
    )
    qs = form.fields["voucher"].queryset
    assert qs.count() == 0


def test_checkout_voucher_form_active_queryset_voucher_active(
    voucher, request_checkout_with_item
):
    assert Voucher.objects.count() == 1
    voucher.start_date = timezone.now()
    voucher.save()
    form = CheckoutVoucherForm(
        {"voucher": voucher.code}, instance=request_checkout_with_item
    )
    qs = form.fields["voucher"].queryset
    assert qs.count() == 1


def test_checkout_voucher_form_active_queryset_after_some_time(
    voucher, request_checkout_with_item
):
    assert Voucher.objects.count() == 1
    voucher.start_date = timezone.now().replace(year=2016, month=6, day=1, hour=0)
    voucher.end_date = timezone.now().replace(year=2016, month=6, day=2, hour=0)
    voucher.save()

    with freeze_time("2016-05-31"):
        form = CheckoutVoucherForm(
            {"voucher": voucher.code}, instance=request_checkout_with_item
        )
        assert form.fields["voucher"].queryset.count() == 0

    with freeze_time("2016-06-01T05:00:00+00:00"):
        form = CheckoutVoucherForm(
            {"voucher": voucher.code}, instance=request_checkout_with_item
        )
        assert form.fields["voucher"].queryset.count() == 1

    with freeze_time("2016-06-03"):
        form = CheckoutVoucherForm(
            {"voucher": voucher.code}, instance=request_checkout_with_item
        )
        assert form.fields["voucher"].queryset.count() == 0


def test_get_voucher_for_checkout(checkout_with_voucher, voucher):
    checkout_voucher = get_voucher_for_checkout(checkout_with_voucher)
    assert checkout_voucher == voucher


def test_get_voucher_for_checkout_expired_voucher(checkout_with_voucher, voucher):
    date_yesterday = timezone.now() - datetime.timedelta(days=1)
    voucher.end_date = date_yesterday
    voucher.save()
    checkout_voucher = get_voucher_for_checkout(checkout_with_voucher)
    assert checkout_voucher is None


def test_get_voucher_for_checkout_no_voucher_code(checkout):
    checkout_voucher = get_voucher_for_checkout(checkout)
    assert checkout_voucher is None


def test_remove_voucher_from_checkout(checkout_with_voucher, voucher_translation_fr):
    checkout = checkout_with_voucher
    remove_voucher_from_checkout(checkout)

    assert not checkout.voucher_code
    assert not checkout.discount_name
    assert not checkout.translated_discount_name
    assert checkout.discount == zero_money()


def test_recalculate_checkout_discount(
    checkout_with_voucher, voucher, voucher_translation_fr, settings
):
    settings.LANGUAGE_CODE = "fr"
    voucher.discount_value = 10
    voucher.save()

    recalculate_checkout_discount(checkout_with_voucher, None)
    assert (
        checkout_with_voucher.translated_discount_name == voucher_translation_fr.name
    )  # noqa
    assert checkout_with_voucher.discount == Money("10.00", "USD")


def test_recalculate_checkout_discount_with_sale(
    checkout_with_voucher_percentage, discount_info
):
    checkout = checkout_with_voucher_percentage
    recalculate_checkout_discount(checkout, [discount_info])
    assert checkout.discount == Money("1.50", "USD")
    assert checkout.get_total(discounts=[discount_info]) == Money("13.50", "USD")


def test_recalculate_checkout_discount_voucher_not_applicable(
    checkout_with_voucher, voucher
):
    checkout = checkout_with_voucher
    voucher.min_spent = Money(100, "USD")
    voucher.save(update_fields=["min_spent_amount", "currency"])

    recalculate_checkout_discount(checkout_with_voucher, None)

    assert not checkout.voucher_code
    assert not checkout.discount_name
    assert checkout.discount == zero_money()


def test_recalculate_checkout_discount_expired_voucher(checkout_with_voucher, voucher):
    checkout = checkout_with_voucher
    date_yesterday = timezone.now() - datetime.timedelta(days=1)
    voucher.end_date = date_yesterday
    voucher.save()

    recalculate_checkout_discount(checkout_with_voucher, None)

    assert not checkout.voucher_code
    assert not checkout.discount_name
    assert checkout.discount == zero_money()


def test_get_checkout_context(checkout_with_voucher):
    line_price = TaxedMoney(net=Money("30.00", "USD"), gross=Money("30.00", "USD"))
    manager = get_extensions_manager()
    expected_data = {
        "checkout": checkout_with_voucher,
        "checkout_are_taxes_handled": manager.taxes_are_enabled(),
        "checkout_lines": [(checkout_with_voucher.lines.first(), line_price)],
        "checkout_shipping_price": zero_taxed_money(),
        "checkout_subtotal": line_price,
        "checkout_total": line_price - checkout_with_voucher.discount,
        "shipping_required": checkout_with_voucher.is_shipping_required(),
        "total_with_shipping": TaxedMoneyRange(start=line_price, stop=line_price),
    }

    data = get_checkout_context(checkout_with_voucher, discounts=None)

    assert data == expected_data


def test_get_checkout_context_with_shipping_range(
    checkout_with_voucher, shipping_method, address, monkeypatch
):
    checkout_with_voucher.shipping_method = shipping_method
    checkout_with_voucher.shipping_address = address
    line_price = TaxedMoney(net=Money("30.00", "USD"), gross=Money("45.00", "USD"))

    monkeypatch.setattr(
        ExtensionsManager, "calculate_checkout_subtotal", Mock(return_value=line_price)
    )

    shipping_range = get_shipping_price_estimate(
        checkout_with_voucher, discounts=None, country_code="US"
    )
    expected_total_with_shipping = TaxedMoneyRange(start=line_price, stop=line_price)
    expected_total_with_shipping += shipping_range

    data = get_checkout_context(
        checkout_with_voucher, discounts=None, shipping_range=shipping_range
    )

    assert data["total_with_shipping"] == expected_total_with_shipping


def test_change_address_in_checkout(checkout, address):
    change_shipping_address_in_checkout(checkout, address)
    change_billing_address_in_checkout(checkout, address)

    checkout.refresh_from_db()
    assert checkout.shipping_address == address
    assert checkout.billing_address == address


def test_change_address_in_checkout_to_none(checkout, address):
    checkout.shipping_address = address
    checkout.billing_address = address.get_copy()
    checkout.save()

    change_shipping_address_in_checkout(checkout, None)
    change_billing_address_in_checkout(checkout, None)

    checkout.refresh_from_db()
    assert checkout.shipping_address is None
    assert checkout.billing_address is None


def test_change_address_in_checkout_to_same(checkout, address):
    checkout.shipping_address = address
    checkout.billing_address = address.get_copy()
    checkout.save(update_fields=["shipping_address", "billing_address"])
    shipping_address_id = checkout.shipping_address.id
    billing_address_id = checkout.billing_address.id

    change_shipping_address_in_checkout(checkout, address)
    change_billing_address_in_checkout(checkout, address)

    checkout.refresh_from_db()
    assert checkout.shipping_address.id == shipping_address_id
    assert checkout.billing_address.id == billing_address_id


def test_change_address_in_checkout_to_other(checkout, address):
    address_id = address.id
    checkout.shipping_address = address
    checkout.billing_address = address.get_copy()
    checkout.save(update_fields=["shipping_address", "billing_address"])
    other_address = Address.objects.create(country=Country("DE"))

    change_shipping_address_in_checkout(checkout, other_address)
    change_billing_address_in_checkout(checkout, other_address)

    checkout.refresh_from_db()
    assert checkout.shipping_address == other_address
    assert checkout.billing_address == other_address
    assert not Address.objects.filter(id=address_id).exists()


def test_change_address_in_checkout_from_user_address_to_other(
    checkout, customer_user, address
):
    address_id = address.id
    checkout.user = customer_user
    checkout.shipping_address = address
    checkout.billing_address = address.get_copy()
    checkout.save(update_fields=["shipping_address", "billing_address"])
    other_address = Address.objects.create(country=Country("DE"))

    change_shipping_address_in_checkout(checkout, other_address)
    change_billing_address_in_checkout(checkout, other_address)

    checkout.refresh_from_db()
    assert checkout.shipping_address == other_address
    assert checkout.billing_address == other_address
    assert Address.objects.filter(id=address_id).exists()


def test_add_voucher_to_checkout(checkout_with_item, voucher):
    assert checkout_with_item.voucher_code is None
    add_voucher_to_checkout(checkout_with_item, voucher)

    assert checkout_with_item.voucher_code == voucher.code


def test_add_voucher_to_checkout_fail(
    checkout_with_item, voucher_with_high_min_spent_amount
):
    with pytest.raises(NotApplicable):
        add_voucher_to_checkout(checkout_with_item, voucher_with_high_min_spent_amount)

    assert checkout_with_item.voucher_code is None


def test_store_user_address_uses_existing_one(address):
    """Ensure storing an address that is already associated to the given user doesn't
    create a new address, but uses the existing one instead.
    """
    user = User.objects.create_user("test@example.com", "password")
    user.addresses.add(address)

    expected_user_addresses_count = 1

    store_user_address(user, address, AddressType.BILLING)

    assert user.addresses.count() == expected_user_addresses_count
    assert user.default_billing_address_id == address.pk


def test_store_user_address_uses_existing_one_despite_duplicated(address):
    """Ensure storing an address handles the possibility of an user
    having the same address associated to them multiple time is handled properly.

    It should use the first identical address associated to the user.
    """
    same_address = Address.objects.create(**address.as_data())
    user = User.objects.create_user("test@example.com", "password")
    user.addresses.set([address, same_address])

    expected_user_addresses_count = 2

    store_user_address(user, address, AddressType.BILLING)

    assert user.addresses.count() == expected_user_addresses_count
    assert user.default_billing_address_id == address.pk


def test_store_user_address_create_new_address_if_not_associated(address):
    """Ensure storing an address that is not associated to the given user
    triggers the creation of a new address, but uses the existing one instead.
    """
    user = User.objects.create_user("test@example.com", "password")
    expected_user_addresses_count = 1

    store_user_address(user, address, AddressType.BILLING)

    assert user.addresses.count() == expected_user_addresses_count
    assert user.default_billing_address_id != address.pk
