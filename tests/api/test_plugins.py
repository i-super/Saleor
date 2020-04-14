import copy

import pytest

from saleor.plugins.base_plugin import ConfigurationTypeField
from saleor.plugins.error_codes import PluginErrorCode
from saleor.plugins.manager import get_plugins_manager
from saleor.plugins.models import PluginConfiguration
from tests.api.utils import assert_no_permission, get_graphql_content
from tests.plugins.sample_plugins import PluginSample
from tests.plugins.utils import get_config_value


@pytest.fixture
def staff_api_client_can_manage_plugins(staff_api_client, permission_manage_plugins):
    staff_api_client.user.user_permissions.add(permission_manage_plugins)
    return staff_api_client


PLUGINS_QUERY = """
    {
      plugins(first:1){
        edges{
          node{
            name
            description
            active
            id
            configuration{
              name
              type
              value
              helpText
              label
            }
          }
        }
      }
    }
"""


def test_query_plugin_configurations(staff_api_client_can_manage_plugins, settings):

    # Enable test plugin
    settings.PLUGINS = ["tests.plugins.sample_plugins.PluginSample"]
    response = staff_api_client_can_manage_plugins.post_graphql(PLUGINS_QUERY)
    content = get_graphql_content(response)

    plugins = content["data"]["plugins"]["edges"]

    assert len(plugins) == 1
    plugin = plugins[0]["node"]
    manager = get_plugins_manager()
    sample_plugin = manager.get_plugin(PluginSample.PLUGIN_NAME)
    confiugration_structure = PluginSample.CONFIG_STRUCTURE

    assert plugin["name"] == sample_plugin.PLUGIN_NAME
    assert plugin["active"] == sample_plugin.DEFAULT_ACTIVE
    assert plugin["description"] == sample_plugin.PLUGIN_DESCRIPTION
    for index, configuration_item in enumerate(plugin["configuration"]):
        assert configuration_item["name"] == sample_plugin.configuration[index]["name"]

        if (
            confiugration_structure[configuration_item["name"]]["type"]
            == ConfigurationTypeField.STRING
        ):
            assert (
                configuration_item["value"]
                == sample_plugin.configuration[index]["value"]
            )
        elif configuration_item["value"] is None:
            assert not sample_plugin.configuration[index]["value"]
        else:
            assert (
                configuration_item["value"]
                == str(sample_plugin.configuration[index]["value"]).lower()
            )


@pytest.mark.parametrize(
    "password, expected_password, api_key, expected_api_key",
    [
        (None, None, None, None),
        ("ABCDEFGHIJ", "", "123456789", "6789"),
        ("", None, "", None),
        (None, None, "1234", "4"),
    ],
)
def test_query_plugins_hides_secret_fields(
    password,
    expected_password,
    api_key,
    expected_api_key,
    staff_api_client,
    permission_manage_plugins,
    settings,
):

    settings.PLUGINS = ["tests.plugins.sample_plugins.PluginSample"]
    manager = get_plugins_manager()
    plugin = manager.get_plugin(PluginSample.PLUGIN_NAME)
    configuration = copy.deepcopy(plugin.configuration)
    for conf_field in configuration:
        if conf_field["name"] == "Password":
            conf_field["value"] = password
        if conf_field["name"] == "API private key":
            conf_field["value"] = api_key
    manager.save_plugin_configuration(
        PluginSample.PLUGIN_NAME, {"active": True, "configuration": configuration}
    )

    staff_api_client.user.user_permissions.add(permission_manage_plugins)
    response = staff_api_client.post_graphql(PLUGINS_QUERY)
    content = get_graphql_content(response)

    plugins = content["data"]["plugins"]["edges"]
    assert len(plugins) == 1
    plugin = plugins[0]["node"]

    for conf_field in plugin["configuration"]:
        if conf_field["name"] == "Password":
            assert conf_field["value"] == expected_password
        if conf_field["name"] == "API private key":
            assert conf_field["value"] == expected_api_key


def test_query_plugin_configurations_as_customer_user(user_api_client, settings):
    settings.PLUGINS = ["tests.plugins.sample_plugins.PluginSample"]
    response = user_api_client.post_graphql(PLUGINS_QUERY)

    assert_no_permission(response)


PLUGIN_QUERY = """
    query plugin($id: ID!){
      plugin(id:$id){
        name
        description
        active
        configuration{
          name
          value
          type
          helpText
          label
        }
      }
    }
"""


@pytest.mark.parametrize(
    "password, expected_password, api_key, expected_api_key",
    [
        (None, None, None, None),
        ("ABCDEFGHIJ", "", "123456789", "6789"),
        ("", None, "", None),
        (None, None, "1234", "4"),
    ],
)
def test_query_plugin_hides_secret_fields(
    password,
    expected_password,
    api_key,
    expected_api_key,
    staff_api_client,
    permission_manage_plugins,
    settings,
):

    settings.PLUGINS = ["tests.api.test_plugins.PluginSample"]
    manager = get_plugins_manager()
    plugin = manager.get_plugin(PluginSample.PLUGIN_NAME)
    configuration = copy.deepcopy(plugin.configuration)
    for conf_field in configuration:
        if conf_field["name"] == "Password":
            conf_field["value"] = password
        if conf_field["name"] == "API private key":
            conf_field["value"] = api_key
    manager.save_plugin_configuration(
        PluginSample.PLUGIN_NAME, {"active": True, "configuration": configuration}
    )

    variables = {"id": plugin.PLUGIN_NAME}
    staff_api_client.user.user_permissions.add(permission_manage_plugins)
    response = staff_api_client.post_graphql(PLUGIN_QUERY, variables)
    content = get_graphql_content(response)

    plugin = content["data"]["plugin"]

    for conf_field in plugin["configuration"]:
        if conf_field["name"] == "Password":
            assert conf_field["value"] == expected_password
        if conf_field["name"] == "API private key":
            assert conf_field["value"] == expected_api_key


def test_query_plugin_configuration(
    staff_api_client, permission_manage_plugins, settings
):
    settings.PLUGINS = ["tests.api.test_plugins.PluginSample"]
    manager = get_plugins_manager()
    sample_plugin = manager.get_plugin(PluginSample.PLUGIN_NAME)

    variables = {"id": sample_plugin.PLUGIN_NAME}
    staff_api_client.user.user_permissions.add(permission_manage_plugins)
    response = staff_api_client.post_graphql(PLUGIN_QUERY, variables)
    content = get_graphql_content(response)
    plugin = content["data"]["plugin"]
    assert plugin["name"] == sample_plugin.PLUGIN_NAME
    assert plugin["active"] == sample_plugin.active
    assert plugin["description"] == sample_plugin.PLUGIN_DESCRIPTION

    configuration_item = plugin["configuration"][0]
    assert configuration_item["name"] == sample_plugin.configuration[0]["name"]
    assert configuration_item["value"] == sample_plugin.configuration[0]["value"]


def test_query_plugin_configuration_for_invalid_plugin_name(
    staff_api_client, permission_manage_plugins
):
    variables = {"id": "fake-name"}
    staff_api_client.user.user_permissions.add(permission_manage_plugins)
    response = staff_api_client.post_graphql(PLUGIN_QUERY, variables)
    content = get_graphql_content(response)
    assert content["data"]["plugin"] is None


def test_query_plugin_configuration_as_customer_user(user_api_client, settings):
    settings.PLUGINS = ["tests.api.test_plugins.PluginSample"]
    manager = get_plugins_manager()
    sample_plugin = manager.get_plugin(PluginSample.PLUGIN_NAME)

    variables = {"id": sample_plugin.PLUGIN_NAME}
    response = user_api_client.post_graphql(PLUGIN_QUERY, variables)

    assert_no_permission(response)


PLUGIN_UPDATE_MUTATION = """
        mutation pluginUpdate(
            $id: ID!, $active: Boolean, $configuration: [ConfigurationItemInput]){
            pluginUpdate(
                id:$id,
                input:{active: $active, configuration: $configuration}
            ){
            plugin{
              name
              active
              configuration{
                name
                value
                type
                helpText
                label
              }
            }
            errors{
              field
              message
            }
            pluginsErrors {
              field
              code
            }
          }
        }
    """


@pytest.mark.parametrize(
    "active, updated_configuration_item",
    [
        (True, {"name": "Username", "value": "user"}),
        (False, {"name": "Username", "value": "admin@example.com"}),
    ],
)
def test_plugin_configuration_update(
    staff_api_client_can_manage_plugins, settings, active, updated_configuration_item
):

    settings.PLUGINS = ["tests.plugins.sample_plugins.PluginSample"]
    manager = get_plugins_manager()
    plugin = manager.get_plugin(PluginSample.PLUGIN_NAME)
    old_configuration = copy.deepcopy(plugin.configuration)

    variables = {
        "id": plugin.PLUGIN_NAME,
        "active": active,
        "configuration": [updated_configuration_item],
    }
    response = staff_api_client_can_manage_plugins.post_graphql(
        PLUGIN_UPDATE_MUTATION, variables
    )
    get_graphql_content(response)

    plugin = PluginConfiguration.objects.get(name=PluginSample.PLUGIN_NAME)
    assert plugin.active == active

    first_configuration_item = plugin.configuration[0]
    assert first_configuration_item["name"] == updated_configuration_item["name"]
    assert first_configuration_item["value"] == updated_configuration_item["value"]

    second_configuration_item = plugin.configuration[1]
    assert second_configuration_item["name"] == old_configuration[1]["name"]
    assert second_configuration_item["value"] == old_configuration[1]["value"]


def test_plugin_configuration_update_containing_invalid_plugin_name(
    staff_api_client_can_manage_plugins,
):
    variables = {
        "id": "fake-name",
        "active": True,
        "configuration": [{"name": "Username", "value": "user"}],
    }
    response = staff_api_client_can_manage_plugins.post_graphql(
        PLUGIN_UPDATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    assert content["data"]["pluginUpdate"]["pluginsErrors"][0] == {
        "field": "id",
        "code": PluginErrorCode.NOT_FOUND.name,
    }


def test_plugin_update_saves_boolean_as_boolean(
    staff_api_client_can_manage_plugins, settings
):
    settings.PLUGINS = ["tests.plugins.sample_plugins.PluginSample"]
    manager = get_plugins_manager()
    plugin = manager.get_plugin(PluginSample.PLUGIN_NAME)
    use_sandbox = get_config_value("Use sandbox", plugin.configuration)
    variables = {
        "id": plugin.PLUGIN_NAME,
        "active": plugin.active,
        "configuration": [{"name": "Use sandbox", "value": True}],
    }
    response = staff_api_client_can_manage_plugins.post_graphql(
        PLUGIN_UPDATE_MUTATION, variables
    )
    content = get_graphql_content(response)
    assert len(content["data"]["pluginUpdate"]["errors"]) == 0
    use_sandbox_new_value = get_config_value("Use sandbox", plugin.configuration)
    assert type(use_sandbox) == type(use_sandbox_new_value)


@pytest.mark.parametrize(
    "plugin_filter, count",
    [
        ({"search": "PluginSample"}, 1),
        ({"search": "description"}, 2),
        ({"active": True}, 2),
        ({"search": "Plugin"}, 2),
        ({"active": "False", "search": "Plugin"}, 1),
    ],
)
def test_plugins_query_with_filter(
    plugin_filter, count, staff_api_client_can_manage_plugins, settings
):
    settings.PLUGINS = [
        "tests.plugins.sample_plugins.PluginSample",
        "tests.plugins.sample_plugins.PluginInactive",
        "tests.plugins.sample_plugins.ActivePlugin",
    ]
    query = """
        query ($filter: PluginFilterInput) {
            plugins(first: 5, filter:$filter) {
                totalCount
                edges {
                    node {
                        id
                    }
                }
            }
        }
    """
    variables = {"filter": plugin_filter}
    response = staff_api_client_can_manage_plugins.post_graphql(query, variables)
    content = get_graphql_content(response)
    assert content["data"]["plugins"]["totalCount"] == count


def test_plugin_configuration_update_as_customer_user(user_api_client, settings):
    settings.PLUGINS = ["tests.plugins.sample_plugins.PluginSample"]
    manager = get_plugins_manager()
    plugin = manager.get_plugin(PluginSample.PLUGIN_NAME)

    variables = {
        "id": plugin.PLUGIN_NAME,
        "active": True,
        "configuration": [{"name": "Username", "value": "user"}],
    }
    response = user_api_client.post_graphql(PLUGIN_UPDATE_MUTATION, variables)

    assert_no_permission(response)


QUERY_PLUGIN_WITH_SORT = """
    query ($sort_by: PluginSortingInput!) {
        plugins(first:5, sortBy: $sort_by) {
            edges{
                node{
                    name
                }
            }
        }
    }
"""


@pytest.mark.parametrize(
    "plugin_sort, result_order",
    [
        (
            {"field": "NAME", "direction": "ASC"},
            ["Active", "PluginInactive", "PluginSample"],
        ),
        (
            {"field": "NAME", "direction": "DESC"},
            ["PluginSample", "PluginInactive", "Active"],
        ),
        (
            {"field": "IS_ACTIVE", "direction": "ASC"},
            ["PluginInactive", "Active", "PluginSample"],
        ),
        (
            {"field": "IS_ACTIVE", "direction": "DESC"},
            ["Active", "PluginSample", "PluginInactive"],
        ),
    ],
)
def test_query_plugins_with_sort(
    plugin_sort, result_order, staff_api_client_can_manage_plugins, settings
):
    settings.PLUGINS = [
        "tests.plugins.sample_plugins.PluginSample",
        "tests.plugins.sample_plugins.PluginInactive",
        "tests.plugins.sample_plugins.ActivePlugin",
    ]
    variables = {"sort_by": plugin_sort}
    response = staff_api_client_can_manage_plugins.post_graphql(
        QUERY_PLUGIN_WITH_SORT, variables
    )
    content = get_graphql_content(response)
    plugins = content["data"]["plugins"]["edges"]

    for order, plugin_name in enumerate(result_order):
        assert plugins[order]["node"]["name"] == plugin_name
