from copy import copy
from decimal import Decimal
from typing import TYPE_CHECKING, Any, List, Union

from django.db.models import QuerySet
from django_countries.fields import Country
from prices import Money, MoneyRange, TaxedMoney, TaxedMoneyRange

from .models import PluginConfiguration

if TYPE_CHECKING:
    from ..core.taxes import TaxType
    from ..checkout.models import Checkout, CheckoutLine
    from ..product.models import Product
    from ..account.models import Address, User
    from ..order.models import OrderLine, Order
    from ..payment.interface import GatewayResponse, PaymentData


class BasePlugin:
    """Abstract class for storing all methods available for any plugin.

    All methods take previous_value parameter.
    previous_value contains a value calculated by the previous plugin in the queue.
    If the plugin is first, it will use default value calculated by the manager.
    """

    PLUGIN_NAME = ""
    CONFIG_STRUCTURE = None

    def __init__(self, *args, **kwargs):
        self._cached_config = None
        self.active = None

    def __str__(self):
        return self.PLUGIN_NAME

    def _initialize_plugin_configuration(self):
        plugin_config_qs = PluginConfiguration.objects.filter(name=self.PLUGIN_NAME)
        plugin_config = self._cached_config or plugin_config_qs.first()

        if plugin_config:
            self._cached_config = plugin_config
            self.active = plugin_config.active

    def calculate_checkout_total(
        self,
        checkout: "Checkout",
        discounts: List["DiscountInfo"],
        previous_value: TaxedMoney,
    ) -> TaxedMoney:
        return NotImplemented

    def calculate_checkout_subtotal(
        self,
        checkout: "Checkout",
        discounts: List["DiscountInfo"],
        previous_value: TaxedMoney,
    ) -> TaxedMoney:
        return NotImplemented

    def calculate_checkout_shipping(
        self,
        checkout: "Checkout",
        discounts: List["DiscountInfo"],
        previous_value: TaxedMoney,
    ) -> TaxedMoney:
        return NotImplemented

    def calculate_order_shipping(
        self, order: "Order", previous_value: TaxedMoney
    ) -> TaxedMoney:
        return NotImplemented

    def calculate_checkout_line_total(
        self,
        checkout_line: "CheckoutLine",
        discounts: List["DiscountInfo"],
        previous_value: TaxedMoney,
    ) -> TaxedMoney:
        return NotImplemented

    def calculate_order_line_unit(
        self, order_line: "OrderLine", previous_value: TaxedMoney
    ) -> TaxedMoney:
        return NotImplemented

    def get_tax_rate_type_choices(
        self, previous_value: List["TaxType"]
    ) -> List["TaxType"]:
        return NotImplemented

    def show_taxes_on_storefront(self, previous_value: bool) -> bool:
        return NotImplemented

    def taxes_are_enabled(self, previous_value: bool) -> bool:
        return NotImplemented

    def apply_taxes_to_shipping_price_range(
        self, prices: MoneyRange, country: Country, previous_value: TaxedMoneyRange
    ) -> TaxedMoneyRange:
        return NotImplemented

    def apply_taxes_to_shipping(
        self, price: Money, shipping_address: "Address", previous_value: TaxedMoney
    ) -> TaxedMoney:
        return NotImplemented

    def apply_taxes_to_product(
        self,
        product: "Product",
        price: Money,
        country: Country,
        previous_value: TaxedMoney,
    ) -> TaxedMoney:
        return NotImplemented

    def preprocess_order_creation(
        self, checkout: "Checkout", discounts: List["DiscountInfo"], previous_value: Any
    ):
        return NotImplemented

    def order_created(self, order: "Order", previous_value: Any):
        return NotImplemented

    def assign_tax_code_to_object_meta(
        self, obj: Union["Product", "ProductType"], tax_code: str, previous_value: Any
    ):
        return NotImplemented

    def get_tax_code_from_object_meta(
        self, obj: Union["Product", "ProductType"], previous_value: "TaxType"
    ) -> "TaxType":
        return NotImplemented

    def get_tax_rate_percentage_value(
        self, obj: Union["Product", "ProductType"], country: Country, previous_value
    ) -> Decimal:
        return NotImplemented

    def customer_created(self, customer: "User", previous_value: Any) -> Any:
        return NotImplemented

    def product_created(self, product: "Product", previous_value: Any) -> Any:
        return NotImplemented

    def order_fully_paid(self, order: "Order", previous_value: Any) -> Any:
        return NotImplemented

    def order_updated(self, order: "Order", previous_value: Any) -> Any:
        return NotImplemented

    def order_cancelled(self, order: "Order", previous_value: Any) -> Any:
        return NotImplemented

    def order_fulfilled(self, order: "Order", previous_value: Any) -> Any:
        return NotImplemented

    def authorize_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return NotImplemented

    def capture_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return NotImplemented

    def refund_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return NotImplemented

    def confirm_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return NotImplemented

    def process_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return NotImplemented

    def list_payment_sources(
        self, customer_id: str, previous_value
    ) -> List["CustomerSource"]:
        return NotImplemented

    def create_form(self, data, payment_information, previous_value):
        return NotImplemented

    def get_client_token(self, token_config, previous_value):
        return NotImplemented

    def get_payment_template(self, previous_value):
        return NotImplemented

    def get_payment_config(self, previous_value):
        return NotImplemented

    @classmethod
    def _update_config_items(
        cls, configuration_to_update: List[dict], current_config: List[dict]
    ):
        for config_item in current_config:
            for config_item_to_update in configuration_to_update:
                if config_item["name"] == config_item_to_update.get("name"):
                    new_value = config_item_to_update.get("value")
                    config_item.update([("value", new_value)])

    @classmethod
    def validate_plugin_configuration(cls, plugin_configuration: "PluginConfiguration"):
        """Validate if provided configuration is correct.

        Raise django.core.exceptions.ValidationError in the other cases
        """
        return

    @classmethod
    def save_plugin_configuration(
        cls, plugin_configuration: "PluginConfiguration", cleaned_data
    ):
        current_config = plugin_configuration.configuration
        configuration_to_update = cleaned_data.get("configuration")
        if configuration_to_update:
            cls._update_config_items(configuration_to_update, current_config)
        if "active" in cleaned_data:
            plugin_configuration.active = cleaned_data["active"]
        cls.validate_plugin_configuration(plugin_configuration)
        plugin_configuration.save()
        if plugin_configuration.configuration:
            # Let's add a translated descriptions and labels
            cls._append_config_structure(plugin_configuration.configuration)
            cls._hide_secret_configuration_fields(plugin_configuration.configuration)
        return plugin_configuration

    @classmethod
    def _get_default_configuration(cls):
        defaults = None
        return defaults

    @classmethod
    def _hide_secret_configuration_fields(cls, configuration: List[dict]):
        return

    @classmethod
    def _append_config_structure(cls, configuration):
        config_structure = getattr(cls, "CONFIG_STRUCTURE") or {}
        for configuration_field in configuration:

            structure_to_add = config_structure.get(configuration_field.get("name"))
            if structure_to_add:
                configuration_field.update(structure_to_add)
        return config_structure

    @classmethod
    def _update_configuration_structure(cls, configuration):
        config_structure = getattr(cls, "CONFIG_STRUCTURE") or {}
        desired_config_keys = set(config_structure.keys())

        config = configuration.configuration or []
        configured_keys = set(d["name"] for d in config)
        missing_keys = desired_config_keys - configured_keys

        if not missing_keys:
            return

        default_config = cls._get_default_configuration()
        if not default_config:
            return

        update_values = [
            copy(k)
            for k in default_config["configuration"]
            if k["name"] in missing_keys
        ]
        config.extend(update_values)

        configuration.configuration = config
        configuration.save(update_fields=["configuration"])

    @classmethod
    def get_plugin_configuration(cls, queryset: QuerySet) -> "PluginConfiguration":
        defaults = cls._get_default_configuration()
        configuration = queryset.get_or_create(name=cls.PLUGIN_NAME, defaults=defaults)[
            0
        ]
        cls._update_configuration_structure(configuration)
        if configuration.configuration:
            # Let's add a translated descriptions and labels
            cls._append_config_structure(configuration.configuration)
            cls._hide_secret_configuration_fields(configuration.configuration)
        return configuration
