from ....checkout import calculations
from ....checkout.fetch import fetch_checkout_info, fetch_checkout_lines
from ....discount import DiscountInfo
from ....plugins.manager import get_plugins_manager
from ...core.utils import to_global_id_or_none
from ...tests.utils import get_graphql_content

# from .mutations.test_checkout_shipping_address_update import (
#     MUTATION_CHECKOUT_SHIPPING_ADDRESS_UPDATE,
# )
# from .test_checkout_lines import MUTATION_CHECKOUT_LINE_DELETE


def test_checkout_totals_use_discounts(
    api_client, checkout_with_item, sale, channel_USD
):
    checkout = checkout_with_item
    # make sure that we're testing a variant that is actually on sale
    product = checkout.lines.first().variant.product
    sale.products.add(product)

    query = """
    query getCheckout($id: ID) {
        checkout(id: $id) {
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

    variables = {"id": to_global_id_or_none(checkout)}
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
            variants_ids=set(),
        )
    ]

    manager = get_plugins_manager()
    lines, _ = fetch_checkout_lines(checkout)
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

    lines, _ = fetch_checkout_lines(checkout)
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
query getCheckout($id: ID) {
  checkout(id: $id) {
    token
    giftCards {
      last4CodeChars
      currentBalance {
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


def test_checkout_get_gift_card_code(user_api_client, checkout_with_gift_card):
    gift_card = checkout_with_gift_card.gift_cards.first()
    variables = {"id": to_global_id_or_none(checkout_with_gift_card)}
    response = user_api_client.post_graphql(
        QUERY_GET_CHECKOUT_GIFT_CARD_CODES, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["checkout"]["giftCards"][0]
    assert data["last4CodeChars"] == gift_card.display_code
    assert data["currentBalance"]["amount"] == gift_card.current_balance.amount


def test_checkout_get_gift_card_codes(
    user_api_client, checkout_with_gift_card, gift_card_created_by_staff
):
    checkout_with_gift_card.gift_cards.add(gift_card_created_by_staff)
    checkout_with_gift_card.save()
    gift_card_first = checkout_with_gift_card.gift_cards.first()
    gift_card_last = checkout_with_gift_card.gift_cards.last()
    variables = {"id": to_global_id_or_none(checkout_with_gift_card)}
    response = user_api_client.post_graphql(
        QUERY_GET_CHECKOUT_GIFT_CARD_CODES, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["checkout"]["giftCards"]
    assert data[0]["last4CodeChars"] == gift_card_first.display_code
    assert data[0]["currentBalance"]["amount"] == gift_card_first.current_balance.amount
    assert data[1]["last4CodeChars"] == gift_card_last.display_code
    assert data[1]["currentBalance"]["amount"] == gift_card_last.current_balance.amount


def test_checkout_get_gift_card_code_without_gift_card(user_api_client, checkout):
    variables = {"id": to_global_id_or_none(checkout)}
    response = user_api_client.post_graphql(
        QUERY_GET_CHECKOUT_GIFT_CARD_CODES, variables
    )
    content = get_graphql_content(response)
    data = content["data"]["checkout"]["giftCards"]
    assert not data
