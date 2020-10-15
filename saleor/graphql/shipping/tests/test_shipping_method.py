import graphene
import pytest
from measurement.measures import Weight

from ....core.weight import WeightUnits
from ....shipping.error_codes import ShippingErrorCode
from ....shipping.utils import get_countries_without_shipping_zone
from ...core.enums import WeightUnitsEnum
from ...tests.utils import assert_negative_positive_decimal_value, get_graphql_content
from ..types import ShippingMethodTypeEnum

SHIPPING_ZONE_QUERY = """
    query ShippingQuery($id: ID!) {
        shippingZone(id: $id) {
            name
            shippingMethods {
                price {
                    amount
                }
                minimumOrderWeight {
                    value
                    unit
                }
                maximumOrderWeight {
                    value
                    unit
                }
            }
            priceRange {
                start {
                    amount
                }
                stop {
                    amount
                }
            }
        }
    }
"""


def test_shipping_zone_query(
    staff_api_client, shipping_zone, permission_manage_shipping
):
    # given
    shipping = shipping_zone
    query = SHIPPING_ZONE_QUERY
    ID = graphene.Node.to_global_id("ShippingZone", shipping.id)
    variables = {"id": ID}

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_shipping]
    )

    # then
    content = get_graphql_content(response)

    shipping_data = content["data"]["shippingZone"]
    assert shipping_data["name"] == shipping.name
    num_of_shipping_methods = shipping_zone.shipping_methods.count()
    assert len(shipping_data["shippingMethods"]) == num_of_shipping_methods
    price_range = shipping.price_range
    data_price_range = shipping_data["priceRange"]
    assert data_price_range["start"]["amount"] == price_range.start.amount
    assert data_price_range["stop"]["amount"] == price_range.stop.amount


def test_shipping_zone_query_weights_returned_in_default_unit(
    staff_api_client, shipping_zone, permission_manage_shipping, site_settings
):
    # given
    shipping = shipping_zone
    shipping_method = shipping.shipping_methods.first()
    shipping_method.minimum_order_weight = Weight(kg=1)
    shipping_method.maximum_order_weight = Weight(kg=10)
    shipping_method.save(update_fields=["minimum_order_weight", "maximum_order_weight"])

    site_settings.default_weight_unit = WeightUnits.GRAM
    site_settings.save(update_fields=["default_weight_unit"])

    query = SHIPPING_ZONE_QUERY
    ID = graphene.Node.to_global_id("ShippingZone", shipping.id)
    variables = {"id": ID}

    # when
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_shipping]
    )

    # then
    content = get_graphql_content(response)

    shipping_data = content["data"]["shippingZone"]
    assert shipping_data["name"] == shipping.name
    num_of_shipping_methods = shipping_zone.shipping_methods.count()
    assert len(shipping_data["shippingMethods"]) == num_of_shipping_methods
    price_range = shipping.price_range
    data_price_range = shipping_data["priceRange"]
    assert data_price_range["start"]["amount"] == price_range.start.amount
    assert data_price_range["stop"]["amount"] == price_range.stop.amount
    assert shipping_data["shippingMethods"][0]["minimumOrderWeight"]["value"] == 1000
    assert (
        shipping_data["shippingMethods"][0]["minimumOrderWeight"]["unit"]
        == WeightUnits.GRAM.upper()
    )
    assert shipping_data["shippingMethods"][0]["maximumOrderWeight"]["value"] == 10000
    assert (
        shipping_data["shippingMethods"][0]["maximumOrderWeight"]["unit"]
        == WeightUnits.GRAM.upper()
    )


def test_shipping_zones_query(
    staff_api_client,
    shipping_zone,
    permission_manage_shipping,
    permission_manage_products,
):
    query = """
    query MultipleShippings {
        shippingZones(first: 100) {
            edges {
              node {
                id
                name
                warehouses {
                  id
                  name
                }
              }
            }
            totalCount
        }
    }
    """
    num_of_shippings = shipping_zone._meta.model.objects.count()
    response = staff_api_client.post_graphql(
        query, permissions=[permission_manage_shipping, permission_manage_products]
    )
    content = get_graphql_content(response)
    assert content["data"]["shippingZones"]["totalCount"] == num_of_shippings


CREATE_SHIPPING_ZONE_QUERY = """
    mutation createShipping(
        $name: String, $default: Boolean, $countries: [String], $addWarehouses: [ID] ){
        shippingZoneCreate(
            input: {
                name: $name, countries: $countries,
                default: $default, addWarehouses: $addWarehouses
            })
        {
            shippingErrors {
                field
                code
            }
            shippingZone {
                name
                countries {
                    code
                }
                default
                warehouses {
                    name
                }
            }
        }
    }
"""


def test_create_shipping_zone(staff_api_client, warehouse, permission_manage_shipping):
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "name": "test shipping",
        "countries": ["PL"],
        "addWarehouses": [warehouse_id],
    }
    response = staff_api_client.post_graphql(
        CREATE_SHIPPING_ZONE_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingZoneCreate"]
    zone = data["shippingZone"]
    assert zone["name"] == "test shipping"
    assert zone["countries"] == [{"code": "PL"}]
    assert zone["warehouses"][0]["name"] == warehouse.name
    assert zone["default"] is False


def test_create_shipping_zone_with_empty_warehouses(
    staff_api_client, permission_manage_shipping
):
    variables = {
        "name": "test shipping",
        "countries": ["PL"],
        "addWarehouses": [],
    }
    response = staff_api_client.post_graphql(
        CREATE_SHIPPING_ZONE_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingZoneCreate"]
    assert not data["shippingErrors"]
    zone = data["shippingZone"]
    assert zone["name"] == "test shipping"
    assert zone["countries"] == [{"code": "PL"}]
    assert not zone["warehouses"]
    assert zone["default"] is False


def test_create_shipping_zone_without_warehouses(
    staff_api_client, permission_manage_shipping
):
    variables = {
        "name": "test shipping",
        "countries": ["PL"],
    }
    response = staff_api_client.post_graphql(
        CREATE_SHIPPING_ZONE_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingZoneCreate"]
    assert not data["shippingErrors"]
    zone = data["shippingZone"]
    assert zone["name"] == "test shipping"
    assert zone["countries"] == [{"code": "PL"}]
    assert not zone["warehouses"]
    assert zone["default"] is False


def test_create_default_shipping_zone(
    staff_api_client, warehouse, permission_manage_shipping
):
    unassigned_countries = set(get_countries_without_shipping_zone())
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "default": True,
        "name": "test shipping",
        "countries": ["PL"],
        "addWarehouses": [warehouse_id],
    }
    response = staff_api_client.post_graphql(
        CREATE_SHIPPING_ZONE_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingZoneCreate"]
    assert not data["shippingErrors"]
    zone = data["shippingZone"]
    assert zone["name"] == "test shipping"
    assert zone["warehouses"][0]["name"] == warehouse.name
    assert zone["default"] is True
    zone_countries = {c.code for c in zone["countries"]}
    assert zone_countries == unassigned_countries


def test_create_duplicated_default_shipping_zone(
    staff_api_client, shipping_zone, permission_manage_shipping
):
    shipping_zone.default = True
    shipping_zone.save()

    variables = {"default": True, "name": "test shipping", "countries": ["PL"]}
    response = staff_api_client.post_graphql(
        CREATE_SHIPPING_ZONE_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingZoneCreate"]
    assert data["shippingErrors"]
    assert data["shippingErrors"][0]["field"] == "default"
    assert data["shippingErrors"][0]["code"] == ShippingErrorCode.ALREADY_EXISTS.name


UPDATE_SHIPPING_ZONE_QUERY = """
    mutation updateShipping(
        $id: ID!
        $name: String
        $default: Boolean
        $countries: [String]
        $addWarehouses: [ID]
        $removeWarehouses: [ID]
    ) {
        shippingZoneUpdate(
            id: $id
            input: {
                name: $name
                default: $default
                countries: $countries
                addWarehouses: $addWarehouses
                removeWarehouses: $removeWarehouses
            }
        ) {
            shippingZone {
                name
                warehouses {
                    name
                    slug
                }
            }
            shippingErrors {
                field
                code
                warehouses
            }
        }
    }
"""


def test_update_shipping_zone(
    staff_api_client, shipping_zone, permission_manage_shipping
):
    name = "Parabolic name"
    shipping_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    variables = {"id": shipping_id, "name": name, "countries": []}
    response = staff_api_client.post_graphql(
        UPDATE_SHIPPING_ZONE_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingZoneUpdate"]
    assert not data["shippingErrors"]
    data = content["data"]["shippingZoneUpdate"]["shippingZone"]
    assert data["name"] == name


def test_update_shipping_zone_default_exists(
    staff_api_client, shipping_zone, permission_manage_shipping
):
    default_zone = shipping_zone
    default_zone.default = True
    default_zone.pk = None
    default_zone.save()
    shipping_zone = shipping_zone.__class__.objects.filter(default=False).get()

    shipping_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    variables = {"id": shipping_id, "name": "Name", "countries": [], "default": True}
    response = staff_api_client.post_graphql(
        UPDATE_SHIPPING_ZONE_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingZoneUpdate"]
    assert data["shippingErrors"][0]["field"] == "default"
    assert data["shippingErrors"][0]["code"] == ShippingErrorCode.ALREADY_EXISTS.name


def test_update_shipping_zone_add_warehouses(
    staff_api_client, shipping_zone, warehouses, permission_manage_shipping,
):
    shipping_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    warehouse_ids = [
        graphene.Node.to_global_id("Warehouse", warehouse.pk)
        for warehouse in warehouses
    ]
    warehouse_names = [warehouse.name for warehouse in warehouses]

    variables = {
        "id": shipping_id,
        "name": shipping_zone.name,
        "addWarehouses": warehouse_ids,
    }
    response = staff_api_client.post_graphql(
        UPDATE_SHIPPING_ZONE_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingZoneUpdate"]
    assert not data["shippingErrors"]
    data = content["data"]["shippingZoneUpdate"]["shippingZone"]
    for response_warehouse in data["warehouses"]:
        assert response_warehouse["name"] in warehouse_names
    assert len(data["warehouses"]) == len(warehouse_names)


def test_update_shipping_zone_add_second_warehouses(
    staff_api_client,
    shipping_zone,
    warehouse,
    warehouse_no_shipping_zone,
    permission_manage_shipping,
):
    shipping_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    warehouse_id = graphene.Node.to_global_id(
        "Warehouse", warehouse_no_shipping_zone.pk
    )
    variables = {
        "id": shipping_id,
        "name": shipping_zone.name,
        "addWarehouses": [warehouse_id],
    }
    response = staff_api_client.post_graphql(
        UPDATE_SHIPPING_ZONE_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingZoneUpdate"]
    assert not data["shippingErrors"]
    data = content["data"]["shippingZoneUpdate"]["shippingZone"]
    assert data["warehouses"][1]["slug"] == warehouse.slug
    assert data["warehouses"][0]["slug"] == warehouse_no_shipping_zone.slug


def test_update_shipping_zone_remove_warehouses(
    staff_api_client, shipping_zone, warehouse, permission_manage_shipping,
):
    shipping_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "id": shipping_id,
        "name": shipping_zone.name,
        "removeWarehouses": [warehouse_id],
    }
    response = staff_api_client.post_graphql(
        UPDATE_SHIPPING_ZONE_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingZoneUpdate"]
    assert not data["shippingErrors"]
    data = content["data"]["shippingZoneUpdate"]["shippingZone"]
    assert not data["warehouses"]


def test_update_shipping_zone_remove_one_warehouses(
    staff_api_client, shipping_zone, warehouses, permission_manage_shipping,
):
    for warehouse in warehouses:
        warehouse.shipping_zones.add(shipping_zone)
    shipping_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouses[0].pk)
    variables = {
        "id": shipping_id,
        "name": shipping_zone.name,
        "removeWarehouses": [warehouse_id],
    }
    response = staff_api_client.post_graphql(
        UPDATE_SHIPPING_ZONE_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingZoneUpdate"]
    assert not data["shippingErrors"]
    data = content["data"]["shippingZoneUpdate"]["shippingZone"]
    assert data["warehouses"][0]["name"] == warehouses[1].name
    assert len(data["warehouses"]) == 1


def test_update_shipping_zone_replace_warehouse(
    staff_api_client,
    shipping_zone,
    warehouse,
    warehouse_no_shipping_zone,
    permission_manage_shipping,
):
    assert shipping_zone.warehouses.first() == warehouse

    shipping_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    add_warehouse_id = graphene.Node.to_global_id(
        "Warehouse", warehouse_no_shipping_zone.pk
    )
    remove_warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "id": shipping_id,
        "name": shipping_zone.name,
        "addWarehouses": [add_warehouse_id],
        "removeWarehouses": [remove_warehouse_id],
    }
    response = staff_api_client.post_graphql(
        UPDATE_SHIPPING_ZONE_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingZoneUpdate"]
    assert not data["shippingErrors"]
    data = content["data"]["shippingZoneUpdate"]["shippingZone"]
    assert data["warehouses"][0]["name"] == warehouse_no_shipping_zone.name
    assert len(data["warehouses"]) == 1


def test_update_shipping_zone_same_warehouse_id_in_add_and_remove(
    staff_api_client, shipping_zone, warehouse, permission_manage_shipping,
):
    shipping_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    warehouse_id = graphene.Node.to_global_id("Warehouse", warehouse.pk)
    variables = {
        "id": shipping_id,
        "name": shipping_zone.name,
        "addWarehouses": [warehouse_id],
        "removeWarehouses": [warehouse_id],
    }
    response = staff_api_client.post_graphql(
        UPDATE_SHIPPING_ZONE_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingZoneUpdate"]
    assert data["shippingErrors"]
    assert data["shippingErrors"][0]["field"] == "removeWarehouses"
    assert (
        data["shippingErrors"][0]["code"]
        == ShippingErrorCode.DUPLICATED_INPUT_ITEM.name
    )
    assert data["shippingErrors"][0]["warehouses"][0] == warehouse_id


def test_delete_shipping_zone(
    staff_api_client, shipping_zone, permission_manage_shipping
):
    query = """
        mutation deleteShippingZone($id: ID!) {
            shippingZoneDelete(id: $id) {
                shippingZone {
                    name
                }
            }
        }
    """
    shipping_zone_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    variables = {"id": shipping_zone_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingZoneDelete"]["shippingZone"]
    assert data["name"] == shipping_zone.name
    with pytest.raises(shipping_zone._meta.model.DoesNotExist):
        shipping_zone.refresh_from_db()


PRICE_BASED_SHIPPING_QUERY = """
    mutation createShippingPrice(
        $type: ShippingMethodTypeEnum, $name: String!, $price: PositiveDecimal,
        $shippingZone: ID!, $minimumOrderPrice: PositiveDecimal,
        $maximumOrderPrice: PositiveDecimal) {
    shippingPriceCreate(input: {
            name: $name, price: $price, shippingZone: $shippingZone,
            minimumOrderPrice: $minimumOrderPrice,
            maximumOrderPrice: $maximumOrderPrice, type: $type}) {
        shippingErrors {
            field
            code
        }
        shippingErrors {
          field
          code
        }
        shippingZone {
            id
        }
        shippingMethod {
            name
            price {
                amount
            }
            minimumOrderPrice {
                amount
            }
            maximumOrderPrice {
                amount
            }
            type
            }
        }
    }
"""


@pytest.mark.parametrize(
    "min_price, max_price, expected_min_price, expected_max_price",
    (
        (10.32, 15.43, {"amount": 10.32}, {"amount": 15.43}),
        (10.33, None, {"amount": 10.33}, None),
    ),
)
def test_create_shipping_method(
    staff_api_client,
    shipping_zone,
    min_price,
    max_price,
    expected_min_price,
    expected_max_price,
    permission_manage_shipping,
):
    name = "DHL"
    price = 12.34
    shipping_zone_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    variables = {
        "shippingZone": shipping_zone_id,
        "name": name,
        "price": price,
        "minimumOrderPrice": min_price,
        "maximumOrderPrice": max_price,
        "type": ShippingMethodTypeEnum.PRICE.name,
    }
    response = staff_api_client.post_graphql(
        PRICE_BASED_SHIPPING_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingPriceCreate"]
    assert "errors" not in data["shippingMethod"]
    assert data["shippingMethod"]["name"] == name
    assert data["shippingMethod"]["price"]["amount"] == float(price)
    assert data["shippingMethod"]["minimumOrderPrice"] == expected_min_price
    assert data["shippingMethod"]["maximumOrderPrice"] == expected_max_price
    assert data["shippingMethod"]["type"] == ShippingMethodTypeEnum.PRICE.name
    assert data["shippingZone"]["id"] == shipping_zone_id


def test_create_shipping_method_with_negative_price(
    staff_api_client, shipping_zone, permission_manage_shipping,
):
    query = PRICE_BASED_SHIPPING_QUERY
    staff_api_client.user.user_permissions.add(permission_manage_shipping)
    name = "DHL"
    price = -12.34
    shipping_zone_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    variables = {
        "shippingZone": shipping_zone_id,
        "name": name,
        "price": price,
        "minimumOrderPrice": 0,
        "maximumOrderPrice": 20,
        "type": ShippingMethodTypeEnum.PRICE.name,
    }

    response = staff_api_client.post_graphql(query, variables)

    assert_negative_positive_decimal_value(response)


def test_create_shipping_price_invalid_price(
    staff_api_client, shipping_zone, permission_manage_shipping,
):
    query = PRICE_BASED_SHIPPING_QUERY
    staff_api_client.user.user_permissions.add(permission_manage_shipping)
    shipping_zone_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    variables = {
        "shippingZone": shipping_zone_id,
        "name": "DHL",
        "price": 1234567891234,
        "minimumOrderPrice": 0,
        "maximumOrderPrice": 20,
        "type": ShippingMethodTypeEnum.PRICE.name,
    }

    response = staff_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    error = content["data"]["shippingPriceCreate"]["shippingErrors"][0]
    assert error["field"] == "price"
    assert error["code"] == ShippingErrorCode.INVALID.name


def test_create_shipping_method_with_to_many_decimal_places_in_price(
    staff_api_client, shipping_zone, permission_manage_shipping,
):  # given
    query = PRICE_BASED_SHIPPING_QUERY
    staff_api_client.user.user_permissions.add(permission_manage_shipping)
    name = "DHL"
    price = 12.345
    shipping_zone_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    variables = {
        "shippingZone": shipping_zone_id,
        "name": name,
        "price": price,
        "minimumOrderPrice": 0,
        "maximumOrderPrice": 20,
        "type": ShippingMethodTypeEnum.PRICE.name,
    }

    # when
    response = staff_api_client.post_graphql(query, variables)

    # then
    content = get_graphql_content(response)
    data = content["data"]["shippingPriceCreate"]
    error = data["shippingErrors"][0]
    assert error["field"] == "price"
    assert error["code"] == ShippingErrorCode.INVALID.name


def test_create_shipping_method_with_to_many_decimal_places_in_minimum_order_price(
    staff_api_client, shipping_zone, permission_manage_shipping,
):  # given
    query = PRICE_BASED_SHIPPING_QUERY
    staff_api_client.user.user_permissions.add(permission_manage_shipping)
    name = "DHL"
    price = 12.34
    shipping_zone_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    variables = {
        "shippingZone": shipping_zone_id,
        "name": name,
        "price": price,
        "minimumOrderPrice": 1.2001,
        "maximumOrderPrice": 20,
        "type": ShippingMethodTypeEnum.PRICE.name,
    }

    # when
    response = staff_api_client.post_graphql(query, variables)

    # then
    content = get_graphql_content(response)
    data = content["data"]["shippingPriceCreate"]
    error = data["shippingErrors"][0]
    assert error["field"] == "minimumOrderPrice"
    assert error["code"] == ShippingErrorCode.INVALID.name


def test_create_shipping_method_with_to_many_decimal_places_in_maximum_order_price(
    staff_api_client, shipping_zone, permission_manage_shipping,
):  # given
    query = PRICE_BASED_SHIPPING_QUERY
    staff_api_client.user.user_permissions.add(permission_manage_shipping)
    name = "DHL"
    price = 12.34
    shipping_zone_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    variables = {
        "shippingZone": shipping_zone_id,
        "name": name,
        "price": price,
        "minimumOrderPrice": 0,
        "maximumOrderPrice": 20.00001,
        "type": ShippingMethodTypeEnum.PRICE.name,
    }

    # when
    response = staff_api_client.post_graphql(query, variables)

    # then
    content = get_graphql_content(response)
    data = content["data"]["shippingPriceCreate"]
    error = data["shippingErrors"][0]
    assert error["field"] == "maximumOrderPrice"
    assert error["code"] == ShippingErrorCode.INVALID.name


def test_create_price_shipping_method_errors(
    shipping_zone, staff_api_client, permission_manage_shipping
):
    shipping_zone_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    variables = {
        "shippingZone": shipping_zone_id,
        "name": "DHL",
        "price": 12.34,
        "minimumOrderPrice": 20,
        "maximumOrderPrice": 10,
        "type": ShippingMethodTypeEnum.PRICE.name,
    }
    response = staff_api_client.post_graphql(
        PRICE_BASED_SHIPPING_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingPriceCreate"]
    assert data["shippingErrors"][0]["code"] == ShippingErrorCode.MAX_LESS_THAN_MIN.name


WEIGHT_BASED_SHIPPING_QUERY = """
    mutation createShippingPrice(
        $type: ShippingMethodTypeEnum, $name: String!, $price: PositiveDecimal,
        $shippingZone: ID!, $maximumOrderWeight: WeightScalar,
        $minimumOrderWeight: WeightScalar) {
        shippingPriceCreate(
            input: {
                name: $name, price: $price, shippingZone: $shippingZone,
                minimumOrderWeight:$minimumOrderWeight,
                maximumOrderWeight: $maximumOrderWeight, type: $type}) {
            shippingErrors {
                field
                code
            }
            shippingMethod {
                minimumOrderWeight {
                    value
                    unit
                }
                maximumOrderWeight {
                    value
                    unit
                }
            }
            shippingZone {
                id
            }
        }
    }
"""


@pytest.mark.parametrize(
    "min_weight, max_weight, expected_min_weight, expected_max_weight",
    (
        (
            10.32,
            15.64,
            {"value": 10.32, "unit": WeightUnitsEnum.KG.name},
            {"value": 15.64, "unit": WeightUnitsEnum.KG.name},
        ),
        (10.92, None, {"value": 10.92, "unit": WeightUnitsEnum.KG.name}, None),
    ),
)
def test_create_weight_based_shipping_method(
    shipping_zone,
    staff_api_client,
    min_weight,
    max_weight,
    expected_min_weight,
    expected_max_weight,
    permission_manage_shipping,
):
    shipping_zone_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    variables = {
        "shippingZone": shipping_zone_id,
        "name": "DHL",
        "price": 12.34,
        "minimumOrderWeight": min_weight,
        "maximumOrderWeight": max_weight,
        "type": ShippingMethodTypeEnum.WEIGHT.name,
    }
    response = staff_api_client.post_graphql(
        WEIGHT_BASED_SHIPPING_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingPriceCreate"]
    assert data["shippingMethod"]["minimumOrderWeight"] == expected_min_weight
    assert data["shippingMethod"]["maximumOrderWeight"] == expected_max_weight
    assert data["shippingZone"]["id"] == shipping_zone_id


def test_create_weight_shipping_method_errors(
    shipping_zone, staff_api_client, permission_manage_shipping
):
    shipping_zone_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    variables = {
        "shippingZone": shipping_zone_id,
        "name": "DHL",
        "price": 12.34,
        "minimumOrderWeight": 20,
        "maximumOrderWeight": 15,
        "type": ShippingMethodTypeEnum.WEIGHT.name,
    }
    response = staff_api_client.post_graphql(
        WEIGHT_BASED_SHIPPING_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingPriceCreate"]
    assert data["shippingErrors"][0]["code"] == ShippingErrorCode.MAX_LESS_THAN_MIN.name


def test_create_shipping_method_with_negative_min_weight(
    shipping_zone, staff_api_client, permission_manage_shipping
):
    shipping_zone_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    variables = {
        "shippingZone": shipping_zone_id,
        "name": "DHL",
        "price": 12.34,
        "minimumOrderWeight": -20,
        "type": ShippingMethodTypeEnum.WEIGHT.name,
    }
    response = staff_api_client.post_graphql(
        WEIGHT_BASED_SHIPPING_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingPriceCreate"]
    error = data["shippingErrors"][0]
    assert error["field"] == "minimumOrderWeight"
    assert error["code"] == ShippingErrorCode.INVALID.name


def test_create_shipping_method_with_negative_max_weight(
    shipping_zone, staff_api_client, permission_manage_shipping
):
    shipping_zone_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    variables = {
        "shippingZone": shipping_zone_id,
        "name": "DHL",
        "price": 12.34,
        "maximumOrderWeight": -15,
        "type": ShippingMethodTypeEnum.WEIGHT.name,
    }
    response = staff_api_client.post_graphql(
        WEIGHT_BASED_SHIPPING_QUERY, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingPriceCreate"]
    error = data["shippingErrors"][0]
    assert error["field"] == "maximumOrderWeight"
    assert error["code"] == ShippingErrorCode.INVALID.name


def test_update_shipping_method(
    staff_api_client, shipping_zone, permission_manage_shipping
):
    query = """
    mutation updateShippingPrice(
        $id: ID!, $price: PositiveDecimal, $shippingZone: ID!,
        $type: ShippingMethodTypeEnum!, $minimumOrderPrice: PositiveDecimal) {
        shippingPriceUpdate(
            id: $id, input: {
                price: $price, shippingZone: $shippingZone,
                type: $type, minimumOrderPrice: $minimumOrderPrice}) {
            shippingErrors {
                field
                code
            }
            shippingZone {
                id
            }
            shippingMethod {
                price {
                    amount
                }
                minimumOrderPrice {
                    amount
                }
                type
            }
        }
    }
    """
    shipping_method = shipping_zone.shipping_methods.first()
    price = 12.34
    assert not str(shipping_method.price) == price
    shipping_zone_id = graphene.Node.to_global_id("ShippingZone", shipping_zone.pk)
    shipping_method_id = graphene.Node.to_global_id(
        "ShippingMethod", shipping_method.pk
    )
    variables = {
        "shippingZone": shipping_zone_id,
        "price": price,
        "id": shipping_method_id,
        "minimumOrderPrice": 12.00,
        "type": ShippingMethodTypeEnum.PRICE.name,
    }
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingPriceUpdate"]
    assert data["shippingMethod"]["price"]["amount"] == float(price)
    assert data["shippingZone"]["id"] == shipping_zone_id


def test_delete_shipping_method(
    staff_api_client, shipping_method, permission_manage_shipping
):
    query = """
        mutation deleteShippingPrice($id: ID!) {
            shippingPriceDelete(id: $id) {
                shippingZone {
                    id
                }
                shippingMethod {
                    id
                }
            }
        }
        """
    shipping_method_id = graphene.Node.to_global_id(
        "ShippingMethod", shipping_method.pk
    )
    shipping_zone_id = graphene.Node.to_global_id(
        "ShippingZone", shipping_method.shipping_zone.pk
    )
    variables = {"id": shipping_method_id}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_shipping]
    )
    content = get_graphql_content(response)
    data = content["data"]["shippingPriceDelete"]
    assert data["shippingMethod"]["id"] == shipping_method_id
    assert data["shippingZone"]["id"] == shipping_zone_id
    with pytest.raises(shipping_method._meta.model.DoesNotExist):
        shipping_method.refresh_from_db()
