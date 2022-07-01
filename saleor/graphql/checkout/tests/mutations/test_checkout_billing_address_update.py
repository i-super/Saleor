from ....core.utils import to_global_id_or_none
from ....tests.utils import get_graphql_content

MUTATION_CHECKOUT_BILLING_ADDRESS_UPDATE = """
    mutation checkoutBillingAddressUpdate(
            $checkoutId: ID, $id: ID, $billingAddress: AddressInput!) {
        checkoutBillingAddressUpdate(
                id: $id,
                checkoutId: $checkoutId,
                billingAddress: $billingAddress
        ){
            checkout {
                token,
                id
            },
            errors {
                field
                code
                message
            }
        }
    }
"""


def test_checkout_billing_address_update_by_id(
    user_api_client, checkout_with_item, graphql_address_data
):
    checkout = checkout_with_item
    assert checkout.shipping_address is None

    query = MUTATION_CHECKOUT_BILLING_ADDRESS_UPDATE
    billing_address = graphql_address_data

    variables = {
        "id": to_global_id_or_none(checkout),
        "billingAddress": billing_address,
    }

    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["checkoutBillingAddressUpdate"]
    assert not data["errors"]
    checkout.refresh_from_db()
    assert checkout.billing_address is not None
    assert checkout.billing_address.first_name == billing_address["firstName"]
    assert checkout.billing_address.last_name == billing_address["lastName"]
    assert (
        checkout.billing_address.street_address_1 == billing_address["streetAddress1"]
    )
    assert (
        checkout.billing_address.street_address_2 == billing_address["streetAddress2"]
    )
    assert checkout.billing_address.postal_code == billing_address["postalCode"]
    assert checkout.billing_address.country == billing_address["country"]
    assert checkout.billing_address.city == billing_address["city"].upper()


def test_checkout_billing_address_update_by_id_without_required_fields(
    user_api_client, checkout_with_item, graphql_address_data
):
    checkout = checkout_with_item
    assert checkout.shipping_address is None

    query = MUTATION_CHECKOUT_BILLING_ADDRESS_UPDATE

    graphql_address_data["streetAddress1"] = ""
    graphql_address_data["streetAddress2"] = ""
    graphql_address_data["postalCode"] = ""

    billing_address = graphql_address_data

    variables = {
        "id": to_global_id_or_none(checkout_with_item),
        "billingAddress": billing_address,
    }

    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["checkoutBillingAddressUpdate"]
    assert data["errors"]
    assert data["errors"] == [
        {
            "code": "REQUIRED",
            "field": "postalCode",
            "message": "This field is required.",
        },
        {
            "code": "REQUIRED",
            "field": "streetAddress1",
            "message": "This field is required.",
        },
    ]


def test_checkout_billing_address_update_by_id_without_street_address_2(
    user_api_client, checkout_with_item, graphql_address_data
):
    checkout = checkout_with_item
    assert checkout.shipping_address is None

    query = MUTATION_CHECKOUT_BILLING_ADDRESS_UPDATE

    graphql_address_data["streetAddress2"] = ""

    billing_address = graphql_address_data

    variables = {
        "id": to_global_id_or_none(checkout_with_item),
        "billingAddress": billing_address,
    }

    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["checkoutBillingAddressUpdate"]
    assert not data["errors"]
    checkout.refresh_from_db()
    assert checkout.billing_address is not None
    assert checkout.billing_address.first_name == billing_address["firstName"]
    assert checkout.billing_address.last_name == billing_address["lastName"]
    assert (
        checkout.billing_address.street_address_1 == billing_address["streetAddress1"]
    )
    assert (
        checkout.billing_address.street_address_2
        == billing_address["streetAddress2"]
        == ""
    )
    assert checkout.billing_address.postal_code == billing_address["postalCode"]
    assert checkout.billing_address.country == billing_address["country"]
    assert checkout.billing_address.city == billing_address["city"].upper()


def test_checkout_billing_address_update(
    user_api_client, checkout_with_item, graphql_address_data
):
    checkout = checkout_with_item
    assert checkout.shipping_address is None
    previous_last_change = checkout.last_change

    query = """
    mutation checkoutBillingAddressUpdate(
            $id: ID, $billingAddress: AddressInput!) {
        checkoutBillingAddressUpdate(
                id: $id, billingAddress: $billingAddress) {
            checkout {
                token,
                id
            },
            errors {
                field,
                message
            }
        }
    }
    """
    billing_address = graphql_address_data

    variables = {
        "id": to_global_id_or_none(checkout_with_item),
        "billingAddress": billing_address,
    }

    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    data = content["data"]["checkoutBillingAddressUpdate"]
    assert not data["errors"]
    checkout.refresh_from_db()
    assert checkout.billing_address is not None
    assert checkout.billing_address.first_name == billing_address["firstName"]
    assert checkout.billing_address.last_name == billing_address["lastName"]
    assert (
        checkout.billing_address.street_address_1 == billing_address["streetAddress1"]
    )
    assert (
        checkout.billing_address.street_address_2 == billing_address["streetAddress2"]
    )
    assert checkout.billing_address.postal_code == billing_address["postalCode"]
    assert checkout.billing_address.country == billing_address["country"]
    assert checkout.billing_address.city == billing_address["city"].upper()
    assert checkout.last_change != previous_last_change
