from datetime import date, timedelta

from .....giftcard import GiftCardEvents
from .....giftcard.error_codes import GiftCardErrorCode
from ....tests.utils import assert_no_permission, get_graphql_content

CREATE_GIFT_CARD_MUTATION = """
    mutation giftCardCreate(
        $balance: PriceInput!, $userEmail: String, $tag: String,
        $expiryDate: Date, $note: String, $isActive: Boolean!
    ){
        giftCardCreate(input: {
                balance: $balance, userEmail: $userEmail, tag: $tag,
                expiryDate: $expiryDate, note: $note,
                isActive: $isActive
            }) {
            giftCard {
                id
                code
                displayCode
                isActive
                expiryDate
                tag
                created
                lastUsedOn
                initialBalance {
                    currency
                    amount
                }
                currentBalance {
                    currency
                    amount
                }
                createdBy {
                    email
                }
                usedBy {
                    email
                }
                createdByEmail
                usedByEmail
                app {
                    name
                }
                product {
                    name
                }
                events {
                    type
                    user {
                        email
                    }
                    app {
                        name
                    }
                    balance {
                        initialBalance {
                            amount
                            currency
                        }
                        oldInitialBalance {
                            amount
                            currency
                        }
                        currentBalance {
                            amount
                            currency
                        }
                        oldCurrentBalance {
                            amount
                            currency
                        }
                    }
                }
            }
            errors {
                field
                message
                code
            }
        }
    }
"""


def test_create_never_expiry_gift_card(
    staff_api_client,
    customer_user,
    permission_manage_gift_card,
    permission_manage_users,
    permission_manage_apps,
):
    # given
    initial_balance = 100
    currency = "USD"
    tag = "gift-card-tag"
    variables = {
        "balance": {
            "amount": initial_balance,
            "currency": currency,
        },
        "userEmail": customer_user.email,
        "tag": tag,
        "note": "This is gift card note that will be save in gift card event.",
        "isActive": True,
    }

    # when
    response = staff_api_client.post_graphql(
        CREATE_GIFT_CARD_MUTATION,
        variables,
        permissions=[
            permission_manage_gift_card,
            permission_manage_users,
            permission_manage_apps,
        ],
    )

    # then
    content = get_graphql_content(response)
    errors = content["data"]["giftCardCreate"]["errors"]
    data = content["data"]["giftCardCreate"]["giftCard"]

    assert not errors
    assert data["code"]
    assert data["displayCode"]
    assert not data["expiryDate"]
    assert data["tag"] == tag
    assert data["createdBy"]["email"] == staff_api_client.user.email
    assert data["createdByEmail"] == staff_api_client.user.email
    assert not data["usedBy"]
    assert not data["usedByEmail"]
    assert not data["app"]
    assert not data["lastUsedOn"]
    assert data["isActive"]
    assert data["initialBalance"]["amount"] == initial_balance
    assert data["currentBalance"]["amount"] == initial_balance

    assert len(data["events"]) == 2
    created_event, sent_event = data["events"]

    assert created_event["type"] == GiftCardEvents.ISSUED.upper()
    assert created_event["user"]["email"] == staff_api_client.user.email
    assert not created_event["app"]
    assert created_event["balance"]["initialBalance"]["amount"] == initial_balance
    assert created_event["balance"]["initialBalance"]["currency"] == currency
    assert created_event["balance"]["currentBalance"]["amount"] == initial_balance
    assert created_event["balance"]["currentBalance"]["currency"] == currency
    assert not created_event["balance"]["oldInitialBalance"]
    assert not created_event["balance"]["oldCurrentBalance"]

    assert sent_event["type"] == GiftCardEvents.SENT_TO_CUSTOMER.upper()
    assert sent_event["user"]["email"] == staff_api_client.user.email
    assert not created_event["app"]


def test_create_gift_card_by_app(
    app_api_client,
    customer_user,
    permission_manage_gift_card,
    permission_manage_users,
):
    # given
    initial_balance = 100
    currency = "USD"
    tag = "gift-card-tag"
    variables = {
        "balance": {
            "amount": initial_balance,
            "currency": currency,
        },
        "userEmail": customer_user.email,
        "tag": tag,
        "note": "This is gift card note that will be save in gift card event.",
        "expiryDate": None,
        "isActive": False,
    }

    # when
    response = app_api_client.post_graphql(
        CREATE_GIFT_CARD_MUTATION,
        variables,
        permissions=[permission_manage_gift_card, permission_manage_users],
    )

    # then
    content = get_graphql_content(response)
    errors = content["data"]["giftCardCreate"]["errors"]
    data = content["data"]["giftCardCreate"]["giftCard"]

    assert not errors
    assert data["code"]
    assert data["displayCode"]
    assert not data["expiryDate"]
    assert data["tag"] == tag
    assert not data["createdBy"]
    assert not data["createdByEmail"]
    assert not data["usedBy"]
    assert not data["usedByEmail"]
    assert data["app"]["name"] == app_api_client.app.name
    assert not data["lastUsedOn"]
    assert data["isActive"] is False
    assert data["initialBalance"]["amount"] == initial_balance
    assert data["currentBalance"]["amount"] == initial_balance

    assert len(data["events"]) == 2
    created_event, sent_event = data["events"]

    assert created_event["type"] == GiftCardEvents.ISSUED.upper()
    assert not created_event["user"]
    assert created_event["app"]["name"] == app_api_client.app.name
    assert created_event["balance"]["initialBalance"]["amount"] == initial_balance
    assert created_event["balance"]["initialBalance"]["currency"] == currency
    assert created_event["balance"]["currentBalance"]["amount"] == initial_balance
    assert created_event["balance"]["currentBalance"]["currency"] == currency
    assert not created_event["balance"]["oldInitialBalance"]
    assert not created_event["balance"]["oldCurrentBalance"]

    assert sent_event["type"] == GiftCardEvents.SENT_TO_CUSTOMER.upper()
    assert not sent_event["user"]
    assert sent_event["app"]["name"] == app_api_client.app.name


def test_create_gift_card_by_customer(api_client, customer_user):
    # given
    initial_balance = 100
    currency = "USD"
    tag = "gift-card-tag"
    variables = {
        "balance": {
            "amount": initial_balance,
            "currency": currency,
        },
        "userEmail": customer_user.email,
        "tag": tag,
        "note": "This is gift card note that will be save in gift card event.",
        "expiryDate": None,
        "isActive": True,
    }

    # when
    response = api_client.post_graphql(
        CREATE_GIFT_CARD_MUTATION,
        variables,
    )

    # then
    assert_no_permission(response)


def test_create_gift_card_no_premissions(staff_api_client):
    # given
    initial_balance = 100
    currency = "USD"
    tag = "gift-card-tag"
    variables = {
        "balance": {
            "amount": initial_balance,
            "currency": currency,
        },
        "tag": tag,
        "note": "This is gift card note that will be save in gift card event.",
        "expiryDate": None,
        "isActive": True,
    }

    # when
    response = staff_api_client.post_graphql(
        CREATE_GIFT_CARD_MUTATION,
        variables,
    )

    # then
    assert_no_permission(response)


def test_create_gift_card_with_too_many_decimal_places_in_balance_amount(
    staff_api_client,
    customer_user,
    permission_manage_gift_card,
    permission_manage_users,
    permission_manage_apps,
):
    # given
    initial_balance = 10.123
    currency = "USD"
    tag = "gift-card-tag"
    variables = {
        "balance": {
            "amount": initial_balance,
            "currency": currency,
        },
        "userEmail": customer_user.email,
        "tag": tag,
        "note": "This is gift card note that will be save in gift card event.",
        "isActive": True,
    }

    # when
    response = staff_api_client.post_graphql(
        CREATE_GIFT_CARD_MUTATION,
        variables,
        permissions=[
            permission_manage_gift_card,
            permission_manage_users,
            permission_manage_apps,
        ],
    )

    # then
    content = get_graphql_content(response)
    errors = content["data"]["giftCardCreate"]["errors"]
    data = content["data"]["giftCardCreate"]["giftCard"]

    assert not data
    assert len(errors) == 1
    assert errors[0]["field"] == "balance"
    assert errors[0]["code"] == GiftCardErrorCode.INVALID.name


def test_create_gift_card_with_malformed_email(
    staff_api_client,
    permission_manage_gift_card,
    permission_manage_users,
    permission_manage_apps,
):
    # given
    initial_balance = 10
    currency = "USD"
    tag = "gift-card-tag"
    variables = {
        "balance": {
            "amount": initial_balance,
            "currency": currency,
        },
        "userEmail": "malformed",
        "tag": tag,
        "note": "This is gift card note that will be save in gift card event.",
        "isActive": True,
    }

    # when
    response = staff_api_client.post_graphql(
        CREATE_GIFT_CARD_MUTATION,
        variables,
        permissions=[
            permission_manage_gift_card,
            permission_manage_users,
            permission_manage_apps,
        ],
    )

    # then
    content = get_graphql_content(response)
    data = content["data"]["giftCardCreate"]["giftCard"]
    errors = content["data"]["giftCardCreate"]["errors"]

    assert not data
    assert len(errors) == 1
    error = errors[0]
    assert error["field"] == "email"
    assert error["code"] == GiftCardErrorCode.INVALID.name


def test_create_gift_card_with_zero_balance_amount(
    staff_api_client,
    customer_user,
    permission_manage_gift_card,
    permission_manage_users,
    permission_manage_apps,
):
    # given
    currency = "USD"
    tag = "gift-card-tag"
    variables = {
        "balance": {
            "amount": 0,
            "currency": currency,
        },
        "userEmail": customer_user.email,
        "tag": tag,
        "note": "This is gift card note that will be save in gift card event.",
        "isActive": True,
    }

    # when
    response = staff_api_client.post_graphql(
        CREATE_GIFT_CARD_MUTATION,
        variables,
        permissions=[
            permission_manage_gift_card,
            permission_manage_users,
            permission_manage_apps,
        ],
    )

    # then
    content = get_graphql_content(response)
    errors = content["data"]["giftCardCreate"]["errors"]
    data = content["data"]["giftCardCreate"]["giftCard"]

    assert not data
    assert len(errors) == 1
    assert errors[0]["field"] == "balance"
    assert errors[0]["code"] == GiftCardErrorCode.INVALID.name


def test_create_gift_card_with_expiry_date(
    staff_api_client,
    customer_user,
    permission_manage_gift_card,
    permission_manage_users,
    permission_manage_apps,
):
    # given
    initial_balance = 100
    currency = "USD"
    date_value = date.today() + timedelta(days=365)
    tag = "gift-card-tag"
    variables = {
        "balance": {
            "amount": initial_balance,
            "currency": currency,
        },
        "userEmail": customer_user.email,
        "tag": tag,
        "note": "This is gift card note that will be save in gift card event.",
        "expiryDate": date_value,
        "isActive": True,
    }

    # when
    response = staff_api_client.post_graphql(
        CREATE_GIFT_CARD_MUTATION,
        variables,
        permissions=[
            permission_manage_gift_card,
            permission_manage_users,
            permission_manage_apps,
        ],
    )

    # then
    content = get_graphql_content(response)
    errors = content["data"]["giftCardCreate"]["errors"]
    data = content["data"]["giftCardCreate"]["giftCard"]

    assert not errors
    assert data["code"]
    assert data["displayCode"]
    assert data["expiryDate"] == date_value.isoformat()

    assert len(data["events"]) == 2
    created_event, sent_event = data["events"]

    assert created_event["type"] == GiftCardEvents.ISSUED.upper()
    assert created_event["user"]["email"] == staff_api_client.user.email
    assert not created_event["app"]
    assert created_event["balance"]["initialBalance"]["amount"] == initial_balance
    assert created_event["balance"]["initialBalance"]["currency"] == currency
    assert created_event["balance"]["currentBalance"]["amount"] == initial_balance
    assert created_event["balance"]["currentBalance"]["currency"] == currency
    assert not created_event["balance"]["oldInitialBalance"]
    assert not created_event["balance"]["oldCurrentBalance"]

    assert sent_event["type"] == GiftCardEvents.SENT_TO_CUSTOMER.upper()
    assert sent_event["user"]["email"] == staff_api_client.user.email
    assert not created_event["app"]


def test_create_gift_card_with_expiry_date_type_date_in_past(
    staff_api_client,
    customer_user,
    permission_manage_gift_card,
    permission_manage_users,
    permission_manage_apps,
):
    # given
    initial_balance = 100
    currency = "USD"
    date_value = date(1999, 1, 1)
    tag = "gift-card-tag"
    variables = {
        "balance": {
            "amount": initial_balance,
            "currency": currency,
        },
        "userEmail": customer_user.email,
        "tag": tag,
        "note": "This is gift card note that will be save in gift card event.",
        "expiryDate": date_value,
        "isActive": True,
    }

    # when
    response = staff_api_client.post_graphql(
        CREATE_GIFT_CARD_MUTATION,
        variables,
        permissions=[
            permission_manage_gift_card,
            permission_manage_users,
            permission_manage_apps,
        ],
    )

    # then
    content = get_graphql_content(response)
    errors = content["data"]["giftCardCreate"]["errors"]
    data = content["data"]["giftCardCreate"]["giftCard"]

    assert not data
    assert len(errors) == 1
    assert errors[0]["field"] == "expiryDate"
    assert errors[0]["code"] == GiftCardErrorCode.INVALID.name
