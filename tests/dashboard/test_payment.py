import pytest
from django.urls import reverse

from saleor.dashboard.forms import ConfigBooleanField, ConfigCharField
from saleor.dashboard.payment.forms import (
    GatewayConfigurationForm,
    create_custom_form_field,
)
from saleor.extensions.models import PluginConfiguration
from saleor.payment.gateways.braintree.plugin import BraintreeGatewayPlugin


@pytest.fixture
def plugin_configuration(db):
    plugin_configuration = PluginConfiguration.objects.create(
        **BraintreeGatewayPlugin._get_default_configuration()
    )

    config = [
        {"name": "Public API key", "value": "123456"},
        {"name": "Secret API key", "value": "654321"},
        {"name": "Merchant ID", "value": "0987654321"},
        {"name": "Use sandbox", "value": False},
        {"name": "Store customers card", "value": False},
        {"name": "Automatic payment capture", "value": False},
        {"name": "Require 3D secure", "value": True},
    ]

    BraintreeGatewayPlugin._update_config_items(
        config, plugin_configuration.configuration
    )
    plugin_configuration.active = True
    plugin_configuration.save()
    return plugin_configuration


@pytest.fixture
def gateway_config_form():
    return GatewayConfigurationForm(BraintreeGatewayPlugin)


@pytest.fixture(autouse=True)
def enable_plugin(settings):
    settings.PLUGINS = [
        "saleor.payment.gateways.braintree.plugin.BraintreeGatewayPlugin"
    ]


@pytest.fixture
def config_char_structure():
    return {
        "name": "Template path",
        "value": "order/payment/braintree.html",
        "type": "String",
        "help_text": "Location of django payment template for gateway.",
        "label": "Template path",
    }


@pytest.fixture(autouse=True)
def staff_user_plugin_manager(staff_user, permission_manage_plugins):
    staff_user.user_permissions.add(permission_manage_plugins)
    return staff_user


def test_configuration_form_get_current_configuration(
    plugin_configuration, gateway_config_form
):
    assert gateway_config_form._get_current_configuration() == plugin_configuration


def test_configuration_form__create_field(config_char_structure):
    template_field = create_custom_form_field(config_char_structure)
    assert isinstance(template_field, ConfigCharField)
    assert template_field.label == config_char_structure["name"]
    assert template_field.initial == config_char_structure["value"]


def test_config_boolean_field_returned_value():
    config_boolean_structure = {
        "name": "Require 3D secure",
        "value": True,
        "type": "Boolean",
        "help_text": "Determines if Saleor should enforce 3D secure during payment.",
        "label": "Require 3D secure",
    }
    boolean_field = ConfigBooleanField(structure=config_boolean_structure)
    assert boolean_field.clean(True) == {
        "name": config_boolean_structure["name"],
        "value": True,
    }
    assert boolean_field.clean(False) == {
        "name": config_boolean_structure["name"],
        "value": False,
    }


def test_config_char_field_returned_value(config_char_structure):
    char_field = ConfigCharField(structure=config_char_structure)
    value = "1234466"
    assert char_field.clean(value) == {
        "name": config_char_structure["name"],
        "value": value,
    }


def test_payment_index_display_only_available_gateways(staff_client):
    url = reverse("dashboard:payments-index")
    response = staff_client.get(url)
    assert response.status_code == 200
    payment_gateways = response.context["payment_gateways"]
    assert len(payment_gateways) == 1
    assert BraintreeGatewayPlugin.PLUGIN_NAME in payment_gateways


def test_configure_payment_gateway_returns_404_when_wrong_plugin_name(staff_client):
    url = reverse("dashboard:configure-payment", args=["wrongValue"])
    response = staff_client.get(url)
    assert response.status_code == 404
