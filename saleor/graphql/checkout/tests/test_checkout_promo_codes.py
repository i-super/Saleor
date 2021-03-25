from datetime import date, timedelta
from decimal import Decimal

import graphene
from prices import Money

from ....checkout import calculations
from ....checkout.fetch import fetch_checkout_info, fetch_checkout_lines
from ....checkout.utils import add_voucher_to_checkout
from ....discount import DiscountInfo, VoucherType
from ....plugins.manager import get_plugins_manager
from ...tests.utils import get_graphql_content
from .test_checkout import (
    MUTATION_CHECKOUT_LINES_DELETE,
    MUTATION_CHECKOUT_SHIPPING_ADDRESS_UPDATE,
)


def test_checkout_lines_delete_with_not_applicable_voucher(
    user_api_client, checkout_with_item, voucher, channel_USD
):
    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout_with_item)
    checkout_info = fetch_checkout_info(checkout_with_item, lines, [], manager)
    subtotal = calculations.checkout_subtotal(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=checkout_with_item.shipping_address,
    )
    voucher.channel_listings.filter(channel=channel_USD).update(
        min_spent_amount=subtotal.gross.amount
    )
    checkout_info = fetch_checkout_info(checkout_with_item, lines, [], manager)

    add_voucher_to_checkout(manager, checkout_info, lines, voucher)
    assert checkout_with_item.voucher_code == voucher.code

    line = checkout_with_item.lines.first()

    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    line_id = graphene.Node.to_global_id("CheckoutLine", line.pk)
    variables = {"checkoutId": checkout_id, "lineId": line_id}
    response = user_api_client.post_graphql(MUTATION_CHECKOUT_LINES_DELETE, variables)
    content = get_graphql_content(response)

    data = content["data"]["checkoutLineDelete"]
    assert not data["errors"]
    checkout_with_item.refresh_from_db()
    assert checkout_with_item.lines.count() == 0
    assert checkout_with_item.voucher_code is None


def test_checkout_shipping_address_update_with_not_applicable_voucher(
    user_api_client,
    checkout_with_item,
    voucher_shipping_type,
    graphql_address_data,
    address_other_country,
    shipping_method,
):
    assert checkout_with_item.shipping_address is None
    assert checkout_with_item.voucher_code is None

    checkout_with_item.shipping_address = address_other_country
    checkout_with_item.shipping_method = shipping_method
    checkout_with_item.save(update_fields=["shipping_address", "shipping_method"])
    assert checkout_with_item.shipping_address.country == address_other_country.country

    voucher = voucher_shipping_type
    assert voucher.countries[0].code == address_other_country.country

    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout_with_item)
    checkout_info = fetch_checkout_info(checkout_with_item, lines, [], manager)
    add_voucher_to_checkout(manager, checkout_info, lines, voucher)
    assert checkout_with_item.voucher_code == voucher.code

    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    new_address = graphql_address_data
    variables = {"checkoutId": checkout_id, "shippingAddress": new_address}
    response = user_api_client.post_graphql(
        MUTATION_CHECKOUT_SHIPPING_ADDRESS_UPDATE, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["checkoutShippingAddressUpdate"]
    assert not data["errors"]

    checkout_with_item.refresh_from_db()
    checkout_with_item.shipping_address.refresh_from_db()

    assert checkout_with_item.shipping_address.country == new_address["country"]
    assert checkout_with_item.voucher_code is None


def test_checkout_totals_use_discounts(
    api_client, checkout_with_item, sale, channel_USD
):
    checkout = checkout_with_item
    # make sure that we're testing a variant that is actually on sale
    product = checkout.lines.first().variant.product
    sale.products.add(product)

    query = """
    query getCheckout($token: UUID) {
        checkout(token: $token) {
            lines {
                totalPrice {
                    gross {
                        amount
                    }
                }
            }
            totalPrice {
                gross {
                    amount
                }
            }
            subtotalPrice {
                gross {
                    amount
                }
            }
        }
    }
    """

    variables = {"token": str(checkout.token)}
    response = api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["checkout"]
    sale_channel_listing = sale.channel_listings.get(channel=channel_USD)
    discounts = [
        DiscountInfo(
            sale=sale,
            channel_listings={channel_USD.slug: sale_channel_listing},
            product_ids={product.id},
            category_ids=set(),
            collection_ids=set(),
        )
    ]

    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout)
    checkout_info = fetch_checkout_info(checkout, lines, discounts, manager)
    taxed_total = calculations.checkout_total(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=checkout.shipping_address,
        discounts=discounts,
    )
    assert data["totalPrice"]["gross"]["amount"] == taxed_total.gross.amount
    assert data["subtotalPrice"]["gross"]["amount"] == taxed_total.gross.amount

    lines = fetch_checkout_lines(checkout)
    checkout_info = fetch_checkout_info(checkout, lines, discounts, manager)
    checkout_line_info = lines[0]
    line_total = calculations.checkout_line_total(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        checkout_line_info=checkout_line_info,
        discounts=discounts,
    )
    assert data["lines"][0]["totalPrice"]["gross"]["amount"] == line_total.gross.amount


QUERY_GET_CHECKOUT_GIFT_CARD_CODES = """
query getCheckout($token: UUID!) {
  checkout(token: $token) {
    token
    giftCards {
      displayCode
      currentBalance {
        amount
      }
    }
  }
}
"""


def test_checkout_get_gift_card_code(user_api_client, checkout_with_gift_card):
    gift_card = checkout_with_gift_card.gift_cards.first()
    variables = {"token": str(checkout_with_gift_card.token)}
    response = user_api_client.post_graphql(
        QUERY_GET_CHECKOUT_GIFT_CARD_CODES, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["checkout"]["giftCards"][0]
    assert data["displayCode"] == gift_card.display_code
    assert data["currentBalance"]["amount"] == gift_card.current_balance.amount


def test_checkout_get_gift_card_codes(
    user_api_client, checkout_with_gift_card, gift_card_created_by_staff
):
    checkout_with_gift_card.gift_cards.add(gift_card_created_by_staff)
    checkout_with_gift_card.save()
    gift_card_first = checkout_with_gift_card.gift_cards.first()
    gift_card_last = checkout_with_gift_card.gift_cards.last()
    variables = {"token": str(checkout_with_gift_card.token)}
    response = user_api_client.post_graphql(
        QUERY_GET_CHECKOUT_GIFT_CARD_CODES, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["checkout"]["giftCards"]
    assert data[0]["displayCode"] == gift_card_first.display_code
    assert data[0]["currentBalance"]["amount"] == gift_card_first.current_balance.amount
    assert data[1]["displayCode"] == gift_card_last.display_code
    assert data[1]["currentBalance"]["amount"] == gift_card_last.current_balance.amount


def test_checkout_get_gift_card_code_without_gift_card(user_api_client, checkout):
    variables = {"token": str(checkout.token)}
    response = user_api_client.post_graphql(
        QUERY_GET_CHECKOUT_GIFT_CARD_CODES, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["checkout"]["giftCards"]
    assert not data


MUTATION_CHECKOUT_ADD_PROMO_CODE = """
    mutation($checkoutId: ID!, $promoCode: String!) {
        checkoutAddPromoCode(
            checkoutId: $checkoutId, promoCode: $promoCode) {
            errors {
                field
                message
            }
            checkout {
                id,
                voucherCode
                giftCards {
                    id
                    displayCode
                }
                totalPrice {
                    gross {
                        amount
                    }
                }
            }
        }
    }
"""


def _mutate_checkout_add_promo_code(client, variables):
    response = client.post_graphql(MUTATION_CHECKOUT_ADD_PROMO_CODE, variables)
    content = get_graphql_content(response)
    return content["data"]["checkoutAddPromoCode"]


def test_checkout_add_voucher_code(api_client, checkout_with_item, voucher):
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {"checkoutId": checkout_id, "promoCode": voucher.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert not data["errors"]
    assert data["checkout"]["id"] == checkout_id
    assert data["checkout"]["voucherCode"] == voucher.code


def test_checkout_add_voucher_code_checkout_with_sale(
    api_client, checkout_with_item, voucher_percentage, discount_info
):
    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout_with_item)
    checkout_info = fetch_checkout_info(checkout_with_item, lines, [], manager)
    address = checkout_with_item.shipping_address
    subtotal = calculations.checkout_subtotal(
        manager=manager, checkout_info=checkout_info, lines=lines, address=address
    )
    subtotal_discounted = calculations.checkout_subtotal(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=address,
        discounts=[discount_info],
    )
    assert subtotal > subtotal_discounted
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {"checkoutId": checkout_id, "promoCode": voucher_percentage.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    checkout_with_item.refresh_from_db()
    assert not data["errors"]
    assert checkout_with_item.voucher_code == voucher_percentage.code
    assert checkout_with_item.discount_amount == Decimal(1.5)


def test_checkout_add_specific_product_voucher_code_checkout_with_sale(
    api_client, checkout_with_item, voucher_specific_product_type, discount_info
):
    voucher = voucher_specific_product_type
    checkout = checkout_with_item
    expected_discount = Decimal(1.5)
    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout)
    checkout_info = fetch_checkout_info(checkout, lines, [], manager)

    subtotal = calculations.checkout_subtotal(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=checkout.shipping_address,
    )
    checkout_info = fetch_checkout_info(checkout, lines, [discount_info], manager)
    subtotal_discounted = calculations.checkout_subtotal(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=checkout.shipping_address,
        discounts=[discount_info],
    )

    assert subtotal > subtotal_discounted
    checkout_id = graphene.Node.to_global_id("Checkout", checkout.pk)
    variables = {"checkoutId": checkout_id, "promoCode": voucher.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    checkout.refresh_from_db()
    assert not data["errors"]
    assert checkout.voucher_code == voucher.code
    assert checkout.discount_amount == expected_discount
    assert checkout.discount == Money(expected_discount, "USD")


def test_checkout_add_products_voucher_code_checkout_with_sale(
    api_client, checkout_with_item, voucher_percentage, discount_info
):
    checkout = checkout_with_item
    product = checkout.lines.first().variant.product
    voucher = voucher_percentage
    voucher.type = VoucherType.SPECIFIC_PRODUCT
    voucher.save()
    voucher.products.add(product)

    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout)
    checkout_info = fetch_checkout_info(checkout, lines, [], manager)

    subtotal = calculations.checkout_subtotal(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=checkout.shipping_address,
    )

    checkout_info = fetch_checkout_info(checkout, lines, [discount_info], manager)
    subtotal_discounted = calculations.checkout_subtotal(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=checkout.shipping_address,
        discounts=[discount_info],
    )
    assert subtotal > subtotal_discounted
    checkout_id = graphene.Node.to_global_id("Checkout", checkout.pk)
    variables = {"checkoutId": checkout_id, "promoCode": voucher.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    checkout.refresh_from_db()
    assert not data["errors"]
    assert checkout.voucher_code == voucher.code
    assert checkout.discount_amount == Decimal(1.5)


def test_checkout_add_collection_voucher_code_checkout_with_sale(
    api_client, checkout_with_item, voucher_percentage, discount_info, collection
):
    checkout = checkout_with_item
    voucher = voucher_percentage
    product = checkout.lines.first().variant.product
    product.collections.add(collection)
    voucher.type = VoucherType.SPECIFIC_PRODUCT
    voucher.save()
    voucher.collections.add(collection)

    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout)
    checkout_info = fetch_checkout_info(checkout, lines, [], manager)
    subtotal = calculations.checkout_subtotal(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=checkout.shipping_address,
    )
    checkout_info = fetch_checkout_info(checkout, lines, [discount_info], manager)
    subtotal_discounted = calculations.checkout_subtotal(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=checkout.shipping_address,
        discounts=[discount_info],
    )
    assert subtotal > subtotal_discounted
    checkout_id = graphene.Node.to_global_id("Checkout", checkout.pk)
    variables = {"checkoutId": checkout_id, "promoCode": voucher.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    checkout.refresh_from_db()
    assert not data["errors"]
    assert checkout.voucher_code == voucher.code
    assert checkout.discount_amount == Decimal(1.5)


def test_checkout_add_category_code_checkout_with_sale(
    api_client, checkout_with_item, voucher_percentage, discount_info
):
    checkout = checkout_with_item
    category = checkout.lines.first().variant.product.category
    voucher = voucher_percentage
    voucher.type = VoucherType.SPECIFIC_PRODUCT
    voucher.save()
    voucher.categories.add(category)

    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout)
    checkout_info = fetch_checkout_info(checkout, lines, [], manager)

    subtotal = calculations.checkout_subtotal(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=checkout.shipping_address,
    )
    checkout_info = fetch_checkout_info(checkout, lines, [discount_info], manager)
    subtotal_discounted = calculations.checkout_subtotal(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=checkout.shipping_address,
        discounts=[discount_info],
    )
    assert subtotal > subtotal_discounted
    checkout_id = graphene.Node.to_global_id("Checkout", checkout.pk)
    variables = {"checkoutId": checkout_id, "promoCode": voucher.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    checkout.refresh_from_db()
    assert not data["errors"]
    assert checkout.voucher_code == voucher.code
    assert checkout.discount_amount == Decimal(1.5)


def test_checkout_add_voucher_code_not_applicable_voucher(
    api_client, checkout_with_item, voucher_with_high_min_spent_amount
):
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {
        "checkoutId": checkout_id,
        "promoCode": voucher_with_high_min_spent_amount.code,
    }
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert data["errors"]
    assert data["errors"][0]["field"] == "promoCode"


def test_checkout_add_voucher_code_not_assigned_to_channel(
    api_client, checkout_with_item, voucher_without_channel
):
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {
        "checkoutId": checkout_id,
        "promoCode": voucher_without_channel.code,
    }
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert data["errors"]
    assert data["errors"][0]["field"] == "promoCode"


def test_checkout_add_gift_card_code(api_client, checkout_with_item, gift_card):
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    gift_card_id = graphene.Node.to_global_id("GiftCard", gift_card.pk)
    variables = {"checkoutId": checkout_id, "promoCode": gift_card.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert not data["errors"]
    assert data["checkout"]["id"] == checkout_id
    assert data["checkout"]["giftCards"][0]["id"] == gift_card_id
    assert data["checkout"]["giftCards"][0]["displayCode"] == gift_card.display_code


def test_checkout_add_many_gift_card_code(
    api_client, checkout_with_gift_card, gift_card_created_by_staff
):
    assert checkout_with_gift_card.gift_cards.count() > 0
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_gift_card.pk)
    gift_card_id = graphene.Node.to_global_id("GiftCard", gift_card_created_by_staff.pk)
    variables = {
        "checkoutId": checkout_id,
        "promoCode": gift_card_created_by_staff.code,
    }
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert not data["errors"]
    assert data["checkout"]["id"] == checkout_id
    gift_card_data = data["checkout"]["giftCards"][-1]
    assert gift_card_data["id"] == gift_card_id
    assert gift_card_data["displayCode"] == gift_card_created_by_staff.display_code


def test_checkout_get_total_with_gift_card(api_client, checkout_with_item, gift_card):
    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout_with_item)
    checkout_info = fetch_checkout_info(checkout_with_item, lines, [], manager)
    taxed_total = calculations.checkout_total(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=checkout_with_item.shipping_address,
    )
    total_with_gift_card = taxed_total.gross.amount - gift_card.current_balance_amount

    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {"checkoutId": checkout_id, "promoCode": gift_card.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert not data["errors"]
    assert data["checkout"]["id"] == checkout_id
    assert not data["checkout"]["giftCards"] == []
    assert data["checkout"]["totalPrice"]["gross"]["amount"] == total_with_gift_card


def test_checkout_get_total_with_many_gift_card(
    api_client, checkout_with_gift_card, gift_card_created_by_staff
):
    manager = get_plugins_manager()
    lines = fetch_checkout_lines(checkout_with_gift_card)
    checkout_info = fetch_checkout_info(checkout_with_gift_card, lines, [], manager)
    taxed_total = calculations.checkout_total(
        manager=manager,
        checkout_info=checkout_info,
        lines=lines,
        address=checkout_with_gift_card.shipping_address,
    )
    taxed_total.gross -= checkout_with_gift_card.get_total_gift_cards_balance()
    taxed_total.net -= checkout_with_gift_card.get_total_gift_cards_balance()
    total_with_gift_card = (
        taxed_total.gross.amount - gift_card_created_by_staff.current_balance_amount
    )

    assert checkout_with_gift_card.gift_cards.count() > 0
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_gift_card.pk)
    variables = {
        "checkoutId": checkout_id,
        "promoCode": gift_card_created_by_staff.code,
    }
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert not data["errors"]
    assert data["checkout"]["id"] == checkout_id
    assert data["checkout"]["totalPrice"]["gross"]["amount"] == total_with_gift_card


def test_checkout_get_total_with_more_money_on_gift_card(
    api_client, checkout_with_item, gift_card_used
):
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {"checkoutId": checkout_id, "promoCode": gift_card_used.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert not data["errors"]
    assert data["checkout"]["id"] == checkout_id
    assert not data["checkout"]["giftCards"] == []
    assert data["checkout"]["totalPrice"]["gross"]["amount"] == 0


def test_checkout_add_same_gift_card_code(api_client, checkout_with_gift_card):
    gift_card = checkout_with_gift_card.gift_cards.first()
    gift_card_id = graphene.Node.to_global_id("GiftCard", gift_card.pk)
    gift_card_count = checkout_with_gift_card.gift_cards.count()
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_gift_card.pk)
    variables = {"checkoutId": checkout_id, "promoCode": gift_card.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert not data["errors"]
    assert data["checkout"]["id"] == checkout_id
    assert data["checkout"]["giftCards"][0]["id"] == gift_card_id
    assert data["checkout"]["giftCards"][0]["displayCode"] == gift_card.display_code
    assert len(data["checkout"]["giftCards"]) == gift_card_count


def test_checkout_add_gift_card_code_in_active_gift_card(
    api_client, checkout_with_item, gift_card
):
    gift_card.is_active = False
    gift_card.save()

    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {"checkoutId": checkout_id, "promoCode": gift_card.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert data["errors"]
    assert data["errors"][0]["field"] == "promoCode"


def test_checkout_add_gift_card_code_in_expired_gift_card(
    api_client, checkout_with_item, gift_card
):
    gift_card.end_date = date.today() - timedelta(days=1)
    gift_card.save()

    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {"checkoutId": checkout_id, "promoCode": gift_card.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert data["errors"]
    assert data["errors"][0]["field"] == "promoCode"


def test_checkout_add_promo_code_invalid_checkout(api_client, voucher):
    variables = {"checkoutId": "unexisting_checkout", "promoCode": voucher.code}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert data["errors"]
    assert data["errors"][0]["field"] == "checkoutId"


def test_checkout_add_promo_code_invalid_promo_code(api_client, checkout_with_item):
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {"checkoutId": checkout_id, "promoCode": "unexisting_code"}
    data = _mutate_checkout_add_promo_code(api_client, variables)

    assert data["errors"]
    assert data["errors"][0]["field"] == "promoCode"


MUTATION_CHECKOUT_REMOVE_PROMO_CODE = """
    mutation($checkoutId: ID!, $promoCode: String!) {
        checkoutRemovePromoCode(
            checkoutId: $checkoutId, promoCode: $promoCode) {
            errors {
                field
                message
            }
            checkout {
                id,
                voucherCode
                giftCards {
                    id
                    displayCode
                }
            }
        }
    }
"""


def _mutate_checkout_remove_promo_code(client, variables):
    response = client.post_graphql(MUTATION_CHECKOUT_REMOVE_PROMO_CODE, variables)
    content = get_graphql_content(response)
    return content["data"]["checkoutRemovePromoCode"]


def test_checkout_remove_voucher_code(api_client, checkout_with_voucher):
    assert checkout_with_voucher.voucher_code is not None

    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_voucher.pk)
    variables = {
        "checkoutId": checkout_id,
        "promoCode": checkout_with_voucher.voucher_code,
    }

    data = _mutate_checkout_remove_promo_code(api_client, variables)

    checkout_with_voucher.refresh_from_db()
    assert not data["errors"]
    assert data["checkout"]["id"] == checkout_id
    assert data["checkout"]["voucherCode"] is None
    assert checkout_with_voucher.voucher_code is None


def test_checkout_remove_voucher_code_with_inactive_channel(
    api_client, checkout_with_voucher
):
    channel = checkout_with_voucher.channel
    channel.is_active = False
    channel.save()

    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_voucher.pk)
    variables = {
        "checkoutId": checkout_id,
        "promoCode": checkout_with_voucher.voucher_code,
    }

    data = _mutate_checkout_remove_promo_code(api_client, variables)

    checkout_with_voucher.refresh_from_db()
    assert not data["errors"]
    assert data["checkout"]["id"] == checkout_id
    assert data["checkout"]["voucherCode"] == checkout_with_voucher.voucher_code


def test_checkout_remove_gift_card_code(api_client, checkout_with_gift_card):
    assert checkout_with_gift_card.gift_cards.count() == 1

    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_gift_card.pk)
    variables = {
        "checkoutId": checkout_id,
        "promoCode": checkout_with_gift_card.gift_cards.first().code,
    }

    data = _mutate_checkout_remove_promo_code(api_client, variables)

    assert data["checkout"]["id"] == checkout_id
    assert data["checkout"]["giftCards"] == []
    assert not checkout_with_gift_card.gift_cards.all().exists()


def test_checkout_remove_one_of_gift_cards(
    api_client, checkout_with_gift_card, gift_card_created_by_staff
):
    checkout_with_gift_card.gift_cards.add(gift_card_created_by_staff)
    checkout_with_gift_card.save()
    gift_card_first = checkout_with_gift_card.gift_cards.first()
    gift_card_last = checkout_with_gift_card.gift_cards.last()

    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_gift_card.pk)
    variables = {"checkoutId": checkout_id, "promoCode": gift_card_first.code}

    data = _mutate_checkout_remove_promo_code(api_client, variables)

    checkout_gift_cards = checkout_with_gift_card.gift_cards
    assert data["checkout"]["id"] == checkout_id
    assert checkout_gift_cards.filter(code=gift_card_last.code).exists()
    assert not checkout_gift_cards.filter(code=gift_card_first.code).exists()


def test_checkout_remove_promo_code_invalid_promo_code(api_client, checkout_with_item):
    checkout_id = graphene.Node.to_global_id("Checkout", checkout_with_item.pk)
    variables = {"checkoutId": checkout_id, "promoCode": "unexisting_code"}

    data = _mutate_checkout_remove_promo_code(api_client, variables)

    assert not data["errors"]
    assert data["checkout"]["id"] == checkout_id


def test_checkout_remove_promo_code_invalid_checkout(api_client, voucher):
    variables = {"checkoutId": "unexisting_checkout", "promoCode": voucher.code}

    data = _mutate_checkout_remove_promo_code(api_client, variables)

    assert data["errors"]
    assert data["errors"][0]["field"] == "checkoutId"
