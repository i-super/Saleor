from typing import TYPE_CHECKING, List

from django.utils.translation import pgettext_lazy

from saleor.extensions import ConfigurationTypeField
from saleor.extensions.base_plugin import BasePlugin

from . import (
    GatewayConfig,
    authorize,
    capture,
    create_form,
    get_client_token,
    list_client_sources,
    process_payment,
    refund,
    void,
)

GATEWAY_NAME = "Braintree"

if TYPE_CHECKING:
    from . import GatewayResponse, PaymentData, TokenConfig
    from django import forms


def require_active_plugin(fn):
    def wrapped(self, *args, **kwargs):
        previous = kwargs.get("previous_value", None)
        self._initialize_plugin_configuration()
        if not self.active:
            return previous
        return fn(self, *args, **kwargs)

    return wrapped


class BraintreeGatewayPlugin(BasePlugin):
    PLUGIN_NAME = GATEWAY_NAME
    CONFIG_STRUCTURE = {
        "Template path": {
            "type": ConfigurationTypeField.STRING,
            "help_text": pgettext_lazy(
                "Plugin help text", "Location of django payment template for gateway."
            ),
            "label": pgettext_lazy("Plugin label", "Template path"),
        },
        "Public API key": {
            "type": ConfigurationTypeField.STRING,
            "help_text": pgettext_lazy(
                "Plugin help text", "Provide Braintree public API key"
            ),
            "label": pgettext_lazy("Plugin label", "Public API key"),
        },
        "Secret API key": {
            "type": ConfigurationTypeField.STRING,
            "help_text": pgettext_lazy(
                "Plugin help text", "Provide Braintree secret API key"
            ),
            "label": pgettext_lazy("Plugin label", "Secret API key"),
        },
        "Merchant ID": {
            "type": ConfigurationTypeField.STRING,
            "help_text": pgettext_lazy(
                "Plugin help text", "Provide Braintree merchant ID"
            ),
            "label": pgettext_lazy("Plugin label", "Merchant ID"),
        },
        "Use sandbox": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": pgettext_lazy(
                "Plugin help text",
                "Determines if Saleor should use Braintree sandbox API.",
            ),
            "label": pgettext_lazy("Plugin label", "Use sandbox"),
        },
        "Store customers card": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": pgettext_lazy(
                "Plugin help text",
                "Determines if Saleor should store cards on payments"
                " in Braintree customer.",
            ),
            "label": pgettext_lazy("Plugin label", "Store customers card"),
        },
        "Automatic payment capture": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": pgettext_lazy(
                "Plugin help text",
                "Determines if Saleor should automaticaly capture payments.",
            ),
            "label": pgettext_lazy("Plugin label", "Automatic payment capture"),
        },
        "Require 3D secure": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": pgettext_lazy(
                "Plugin help text",
                "Determines if Saleor should enforce 3D secure during payment.",
            ),
            "label": pgettext_lazy("Plugin label", "Require 3D secure"),
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = GatewayConfig(
            gateway_name=GATEWAY_NAME,
            auto_capture=True,
            template_path="",
            connection_params={},
        )

    def _initialize_plugin_configuration(self):
        super()._initialize_plugin_configuration()

        if self._cached_config and self._cached_config.configuration:
            configuration = self._cached_config.configuration

            configuration = {item["name"]: item["value"] for item in configuration}
            self.config = GatewayConfig(
                gateway_name=GATEWAY_NAME,
                auto_capture=configuration["Automatic payment capture"],
                connection_params={
                    "sandbox_mode": configuration["Use sandbox"],
                    "merchant_id": configuration["Merchant ID"],
                    "public_key": configuration["Public API key"],
                    "private_key": configuration["Secret API key"],
                },
                template_path=configuration["Template path"],
                store_customer=configuration["Store customers card"],
                require_3d_secure=configuration["Require 3D secure"],
            )

    @classmethod
    def _get_default_configuration(cls):
        defaults = {
            "name": cls.PLUGIN_NAME,
            "description": "",
            "active": False,
            "configuration": [
                {"name": "Template path", "value": "order/payment/braintree.html"},
                {"name": "Public API key", "value": ""},
                {"name": "Secret API key", "value": ""},
                {"name": "Use sandbox", "value": True},
                {"name": "Merchant ID", "value": ""},
                {"name": "Store customers card", "value": False},
                {"name": "Automatic payment capture", "value": True},
                {"name": "Require 3D secure", "value": False},
            ],
        }
        return defaults

    def _get_gateway_config(self) -> GatewayConfig:
        return self.config

    @require_active_plugin
    def authorize_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return authorize(payment_information, self._get_gateway_config())

    @require_active_plugin
    def capture_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return capture(payment_information, self._get_gateway_config())

    @require_active_plugin
    def refund_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return refund(payment_information, self._get_gateway_config())

    @require_active_plugin
    def void_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return void(payment_information, self._get_gateway_config())

    @require_active_plugin
    def process_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return process_payment(payment_information, self._get_gateway_config())

    @require_active_plugin
    def list_payment_sources(
        self, customer_id: str, previous_value
    ) -> List["CustomerSource"]:
        sources = list_client_sources(self._get_gateway_config(), customer_id)
        previous_value.extend(sources)
        return previous_value

    @require_active_plugin
    def create_form(
        self, data, payment_information: "PaymentData", previous_value
    ) -> "forms.Form":
        return create_form(data, payment_information)

    @require_active_plugin
    def get_client_token(self, token_config: "TokenConfig", previous_value):
        return get_client_token(self._get_gateway_config(), token_config)

    @require_active_plugin
    def get_payment_template(self, previous_value) -> str:
        return self._get_gateway_config().template_path

    @require_active_plugin
    def get_payment_config(self, previous_value):
        config = self._get_gateway_config()
        return [
            {"field": "store_customer_card", "value": config.store_customer},
            {"field": "client_token", "value": get_client_token(config=config)},
        ]
