from decimal import Decimal
from typing import TYPE_CHECKING, Iterable, Optional, Tuple, Union

from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from django_countries.fields import Country
from prices import Money, TaxedMoney

from ...account.models import User
from ...core.taxes import TaxType
from ..base_plugin import BasePlugin, ConfigurationTypeField, ExternalAccessTokens

if TYPE_CHECKING:
    # flake8: noqa
    from ...account.models import Address
    from ...channel.models import Channel
    from ...checkout.fetch import CheckoutInfo, CheckoutLineInfo
    from ...checkout.models import Checkout
    from ...discount import DiscountInfo
    from ...order.models import Order, OrderLine
    from ...product.models import Product, ProductType, ProductVariant


class PluginSample(BasePlugin):
    PLUGIN_ID = "plugin.sample"
    PLUGIN_NAME = "PluginSample"
    PLUGIN_DESCRIPTION = "Test plugin description"
    DEFAULT_ACTIVE = True
    CONFIGURATION_PER_CHANNEL = False
    DEFAULT_CONFIGURATION = [
        {"name": "Username", "value": "admin"},
        {"name": "Password", "value": None},
        {"name": "Use sandbox", "value": False},
        {"name": "API private key", "value": None},
    ]

    CONFIG_STRUCTURE = {
        "Username": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Username input field",
            "label": "Username",
        },
        "Password": {
            "type": ConfigurationTypeField.PASSWORD,
            "help_text": "Password input field",
            "label": "Password",
        },
        "Use sandbox": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": "Use sandbox",
            "label": "Use sandbox",
        },
        "API private key": {
            "type": ConfigurationTypeField.SECRET,
            "help_text": "API key",
            "label": "Private key",
        },
        "certificate": {
            "type": ConfigurationTypeField.SECRET_MULTILINE,
            "help_text": "",
            "label": "Multiline certificate",
        },
    }

    def webhook(self, request: WSGIRequest, path: str, previous_value) -> HttpResponse:
        if path == "/webhook/paid":
            return JsonResponse(data={"received": True, "paid": True})
        if path == "/webhook/failed":
            return JsonResponse(data={"received": True, "paid": False})
        return HttpResponseNotFound()

    def calculate_checkout_total(
        self, checkout_info, lines, address, discounts, previous_value
    ):
        total = Money("1.0", currency=checkout_info.checkout.currency)
        return TaxedMoney(total, total)

    def calculate_checkout_shipping(
        self, checkout_info, lines, address, discounts, previous_value
    ):
        price = Money("1.0", currency=checkout_info.checkout.currency)
        return TaxedMoney(price, price)

    def calculate_order_shipping(self, order, previous_value):
        price = Money("1.0", currency=order.currency)
        return TaxedMoney(price, price)

    def calculate_checkout_line_total(
        self,
        checkout_info: "CheckoutInfo",
        lines: Iterable["CheckoutLineInfo"],
        checkout_line_info: "CheckoutLineInfo",
        address: Optional["Address"],
        discounts: Iterable["DiscountInfo"],
        previous_value: TaxedMoney,
    ):
        price = Money("1.0", currency=checkout_info.checkout.currency)
        return TaxedMoney(price, price)

    def calculate_order_line_total(
        self,
        order: "Order",
        order_line: "OrderLine",
        variant: "ProductVariant",
        product: "Product",
        previous_value: TaxedMoney,
    ) -> TaxedMoney:
        price = Money("1.0", currency=order.currency)
        return TaxedMoney(price, price)

    def calculate_checkout_line_unit_price(
        self,
        checkout_info: "CheckoutInfo",
        lines: Iterable["CheckoutLineInfo"],
        checkout_line_info: "CheckoutLineInfo",
        address: Optional["Address"],
        discounts: Iterable["DiscountInfo"],
        previous_value: TaxedMoney,
    ):
        currency = checkout_info.checkout.currency
        price = Money("10.0", currency)
        return TaxedMoney(price, price)

    def calculate_order_line_unit(
        self,
        order: "Order",
        order_line: "OrderLine",
        variant: "ProductVariant",
        product: "Product",
        previous_value: TaxedMoney,
    ):
        currency = order_line.unit_price.currency
        price = Money("1.0", currency)
        return TaxedMoney(price, price)

    def get_tax_rate_type_choices(self, previous_value):
        return [TaxType(code="123", description="abc")]

    def show_taxes_on_storefront(self, previous_value: bool) -> bool:
        return True

    def apply_taxes_to_product(self, product, price, country, previous_value, **kwargs):
        price = Money("1.0", price.currency)
        return TaxedMoney(price, price)

    def apply_taxes_to_shipping(
        self, price, shipping_address, previous_value
    ) -> TaxedMoney:
        price = Money("1.0", price.currency)
        return TaxedMoney(price, price)

    def get_tax_rate_percentage_value(
        self, obj: Union["Product", "ProductType"], country: Country, previous_value
    ) -> Decimal:
        return Decimal("15.0").quantize(Decimal("1."))

    def external_authentication_url(
        self, data: dict, request: WSGIRequest, previous_value
    ) -> dict:
        return {"authorizeUrl": "http://www.auth.provider.com/authorize/"}

    def external_obtain_access_tokens(
        self, data: dict, request: WSGIRequest, previous_value
    ) -> ExternalAccessTokens:
        return ExternalAccessTokens(
            token="token1", refresh_token="refresh2", csrf_token="csrf3"
        )

    def external_refresh(
        self, data: dict, request: WSGIRequest, previous_value
    ) -> ExternalAccessTokens:
        return ExternalAccessTokens(
            token="token4", refresh_token="refresh5", csrf_token="csrf6"
        )

    def external_verify(
        self, data: dict, request: WSGIRequest, previous_value
    ) -> Tuple[Optional[User], dict]:
        user = User.objects.get()
        return user, {"some_data": "data"}

    def authenticate_user(
        self, request: WSGIRequest, previous_value
    ) -> Optional["User"]:
        return User.objects.filter().first()

    def external_logout(self, data: dict, request: WSGIRequest, previous_value) -> dict:
        return {"logoutUrl": "http://www.auth.provider.com/logout/"}

    def get_checkout_line_tax_rate(
        self,
        checkout_info: "CheckoutInfo",
        lines: Iterable["CheckoutLineInfo"],
        checkout_line_info: "CheckoutLineInfo",
        address: Optional["Address"],
        discounts: Iterable["DiscountInfo"],
        previous_value: Decimal,
    ) -> Decimal:
        return Decimal("0.080").quantize(Decimal(".01"))

    def get_order_line_tax_rate(
        self,
        order: "Order",
        product: "Product",
        variant: "ProductVariant",
        address: Optional["Address"],
        previous_value: Decimal,
    ) -> Decimal:
        return Decimal("0.080").quantize(Decimal(".01"))

    def get_checkout_shipping_tax_rate(
        self,
        checkout_info: "CheckoutInfo",
        lines: Iterable["CheckoutLineInfo"],
        address: Optional["Address"],
        discounts: Iterable["DiscountInfo"],
        previous_value: Decimal,
    ):
        return Decimal("0.080").quantize(Decimal(".01"))

    def get_order_shipping_tax_rate(self, order: "Order", previous_value: Decimal):
        return Decimal("0.080").quantize(Decimal(".01"))


class ChannelPluginSample(PluginSample):
    PLUGIN_ID = "channel.plugin.sample"
    PLUGIN_NAME = "Channel Plugin"
    PLUGIN_DESCRIPTION = "Test channel plugin"
    DEFAULT_ACTIVE = True
    CONFIGURATION_PER_CHANNEL = True
    DEFAULT_CONFIGURATION = [{"name": "input-per-channel", "value": None}]
    CONFIG_STRUCTURE = {
        "input-per-channel": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Test input",
            "label": "Input per channel",
        }
    }


class InactiveChannelPluginSample(PluginSample):
    PLUGIN_ID = "channel.plugin.inactive.sample"
    PLUGIN_NAME = "Inactive Channel Plugin"
    PLUGIN_DESCRIPTION = "Test channel plugin"
    DEFAULT_ACTIVE = False
    CONFIGURATION_PER_CHANNEL = True
    DEFAULT_CONFIGURATION = [{"name": "input-per-channel", "value": None}]
    CONFIG_STRUCTURE = {
        "input-per-channel": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Test input",
            "label": "Input per channel",
        }
    }


class PluginInactive(BasePlugin):
    PLUGIN_ID = "mirumee.taxes.plugin.inactive"
    PLUGIN_NAME = "PluginInactive"
    PLUGIN_DESCRIPTION = "Test plugin description_2"
    CONFIGURATION_PER_CHANNEL = False
    DEFAULT_ACTIVE = False

    def external_obtain_access_tokens(
        self, data: dict, request: WSGIRequest, previous_value
    ) -> ExternalAccessTokens:
        return ExternalAccessTokens(
            token="token1", refresh_token="refresh2", csrf_token="csrf3"
        )


class ActivePlugin(BasePlugin):
    PLUGIN_ID = "mirumee.x.plugin.active"
    PLUGIN_NAME = "Active"
    PLUGIN_DESCRIPTION = "Not working"
    DEFAULT_ACTIVE = True
    CONFIGURATION_PER_CHANNEL = False


class ActivePaymentGateway(BasePlugin):
    PLUGIN_ID = "mirumee.gateway.active"
    CLIENT_CONFIG = [
        {"field": "foo", "value": "bar"},
    ]
    PLUGIN_NAME = "braintree"
    DEFAULT_ACTIVE = True
    SUPPORTED_CURRENCIES = ["USD"]

    def process_payment(self, payment_information, previous_value):
        pass

    def get_supported_currencies(self, previous_value):
        return self.SUPPORTED_CURRENCIES

    def get_payment_config(self, previous_value):
        return self.CLIENT_CONFIG


class ActiveDummyPaymentGateway(BasePlugin):
    PLUGIN_ID = "sampleDummy.active"
    CLIENT_CONFIG = [
        {"field": "foo", "value": "bar"},
    ]
    PLUGIN_NAME = "SampleDummy"
    DEFAULT_ACTIVE = True
    SUPPORTED_CURRENCIES = ["EUR", "USD"]

    def process_payment(self, payment_information, previous_value):
        pass

    def get_supported_currencies(self, previous_value):
        return self.SUPPORTED_CURRENCIES

    def get_payment_config(self, previous_value):
        return self.CLIENT_CONFIG


class InactivePaymentGateway(BasePlugin):
    PLUGIN_ID = "gateway.inactive"
    PLUGIN_NAME = "stripe"

    def process_payment(self, payment_information, previous_value):
        pass
