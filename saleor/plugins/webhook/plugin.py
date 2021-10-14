import json
import logging
from typing import TYPE_CHECKING, Any, List, Optional, Union

from ...app.models import App
from ...core.notify_events import NotifyEventType
from ...core.utils.json_serializer import CustomJsonEncoder
from ...payment import PaymentError, TransactionKind
from ...webhook.event_types import WebhookEventType
from ...webhook.payloads import (
    generate_checkout_payload,
    generate_customer_payload,
    generate_fulfillment_payload,
    generate_invoice_payload,
    generate_list_gateways_payload,
    generate_order_payload,
    generate_page_payload,
    generate_payment_payload,
    generate_product_deleted_payload,
    generate_product_payload,
    generate_product_variant_payload,
    generate_product_variant_with_stock_payload,
    generate_sale_payload,
    generate_translation_payload,
)
from ..base_plugin import BasePlugin
from .tasks import trigger_webhook_sync, trigger_webhooks_for_event
from .utils import (
    from_payment_app_id,
    parse_list_payment_gateways_response,
    parse_list_shipping_methods_response,
    parse_payment_action_response,
)

if TYPE_CHECKING:
    from ...account.models import User
    from ...checkout.models import Checkout
    from ...discount.models import Sale
    from ...graphql.discount.mutations import NodeCatalogueInfo
    from ...invoice.models import Invoice
    from ...order.models import Fulfillment, Order
    from ...page.models import Page
    from ...payment.interface import GatewayResponse, PaymentData, PaymentGateway
    from ...product.models import Product, ProductVariant
    from ...shipping.interface import ShippingMethodData
    from ...translation.models import Translation
    from ...warehouse.models import Stock


logger = logging.getLogger(__name__)


class WebhookPlugin(BasePlugin):
    PLUGIN_ID = "mirumee.webhooks"
    PLUGIN_NAME = "Webhooks"
    DEFAULT_ACTIVE = True
    CONFIGURATION_PER_CHANNEL = False

    @classmethod
    def check_plugin_id(cls, plugin_id: str) -> bool:
        is_webhook_plugin = super().check_plugin_id(plugin_id)
        if not is_webhook_plugin:
            payment_app_data = from_payment_app_id(plugin_id)
            return payment_app_data is not None
        return is_webhook_plugin

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.active = True

    def order_created(self, order: "Order", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        order_data = generate_order_payload(order)
        trigger_webhooks_for_event.delay(WebhookEventType.ORDER_CREATED, order_data)

    def order_confirmed(self, order: "Order", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        order_data = generate_order_payload(order)
        trigger_webhooks_for_event.delay(WebhookEventType.ORDER_CONFIRMED, order_data)

    def order_fully_paid(self, order: "Order", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        order_data = generate_order_payload(order)
        trigger_webhooks_for_event.delay(WebhookEventType.ORDER_FULLY_PAID, order_data)

    def order_updated(self, order: "Order", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        order_data = generate_order_payload(order)
        trigger_webhooks_for_event.delay(WebhookEventType.ORDER_UPDATED, order_data)

    def sale_created(
        self, sale: "Sale", current_catalogue: "NodeCatalogueInfo", previous_value: Any
    ) -> Any:
        if not self.active:
            return previous_value
        sale_data = generate_sale_payload(
            sale, previous_catalogue=None, current_catalogue=current_catalogue
        )
        trigger_webhooks_for_event.delay(WebhookEventType.SALE_CREATED, sale_data)

    def sale_updated(
        self,
        sale: "Sale",
        previous_catalogue: "NodeCatalogueInfo",
        current_catalogue: "NodeCatalogueInfo",
        previous_value: Any,
    ) -> Any:
        if not self.active:
            return previous_value
        sale_data = generate_sale_payload(sale, previous_catalogue, current_catalogue)
        trigger_webhooks_for_event.delay(WebhookEventType.SALE_UPDATED, sale_data)

    def sale_deleted(
        self, sale: "Sale", previous_catalogue: "NodeCatalogueInfo", previous_value: Any
    ) -> Any:
        if not self.active:
            return previous_value
        sale_data = generate_sale_payload(sale, previous_catalogue=previous_catalogue)
        trigger_webhooks_for_event.delay(WebhookEventType.SALE_DELETED, sale_data)

    def invoice_request(
        self,
        order: "Order",
        invoice: "Invoice",
        number: Optional[str],
        previous_value: Any,
    ) -> Any:
        if not self.active:
            return previous_value
        invoice_data = generate_invoice_payload(invoice)
        trigger_webhooks_for_event.delay(
            WebhookEventType.INVOICE_REQUESTED, invoice_data
        )

    def invoice_delete(self, invoice: "Invoice", previous_value: Any):
        if not self.active:
            return previous_value
        invoice_data = generate_invoice_payload(invoice)
        trigger_webhooks_for_event.delay(WebhookEventType.INVOICE_DELETED, invoice_data)

    def invoice_sent(self, invoice: "Invoice", email: str, previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        invoice_data = generate_invoice_payload(invoice)
        trigger_webhooks_for_event.delay(WebhookEventType.INVOICE_SENT, invoice_data)

    def order_cancelled(self, order: "Order", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        order_data = generate_order_payload(order)
        trigger_webhooks_for_event.delay(WebhookEventType.ORDER_CANCELLED, order_data)

    def order_fulfilled(self, order: "Order", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        order_data = generate_order_payload(order)
        trigger_webhooks_for_event.delay(WebhookEventType.ORDER_FULFILLED, order_data)

    def draft_order_created(self, order: "Order", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        order_data = generate_order_payload(order)
        trigger_webhooks_for_event.delay(
            WebhookEventType.DRAFT_ORDER_CREATED, order_data
        )

    def draft_order_updated(self, order: "Order", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        order_data = generate_order_payload(order)
        trigger_webhooks_for_event.delay(
            WebhookEventType.DRAFT_ORDER_UPDATED, order_data
        )

    def draft_order_deleted(self, order: "Order", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        order_data = generate_order_payload(order)
        trigger_webhooks_for_event.delay(
            WebhookEventType.DRAFT_ORDER_DELETED, order_data
        )

    def fulfillment_created(self, fulfillment: "Fulfillment", previous_value):
        if not self.active:
            return previous_value
        fulfillment_data = generate_fulfillment_payload(fulfillment)
        trigger_webhooks_for_event.delay(
            WebhookEventType.FULFILLMENT_CREATED, fulfillment_data
        )

    def fulfillment_canceled(self, fulfillment: "Fulfillment", previous_value):
        if not self.active:
            return previous_value
        fulfillment_data = generate_fulfillment_payload(fulfillment)
        trigger_webhooks_for_event.delay(
            WebhookEventType.FULFILLMENT_CANCELED, fulfillment_data
        )

    def customer_created(self, customer: "User", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        customer_data = generate_customer_payload(customer)
        trigger_webhooks_for_event.delay(
            WebhookEventType.CUSTOMER_CREATED, customer_data
        )

    def customer_updated(self, customer: "User", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        customer_data = generate_customer_payload(customer)
        trigger_webhooks_for_event.delay(
            WebhookEventType.CUSTOMER_UPDATED, customer_data
        )

    def product_created(self, product: "Product", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        product_data = generate_product_payload(product)
        trigger_webhooks_for_event.delay(WebhookEventType.PRODUCT_CREATED, product_data)

    def product_updated(self, product: "Product", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        product_data = generate_product_payload(product)
        trigger_webhooks_for_event.delay(WebhookEventType.PRODUCT_UPDATED, product_data)

    def product_deleted(
        self, product: "Product", variants: List[int], previous_value: Any
    ) -> Any:
        if not self.active:
            return previous_value
        product_data = generate_product_deleted_payload(product, variants)
        trigger_webhooks_for_event.delay(WebhookEventType.PRODUCT_DELETED, product_data)

    def product_variant_created(
        self, product_variant: "ProductVariant", previous_value: Any
    ) -> Any:
        if not self.active:
            return previous_value
        product_variant_data = generate_product_variant_payload([product_variant])
        trigger_webhooks_for_event.delay(
            WebhookEventType.PRODUCT_VARIANT_CREATED, product_variant_data
        )

    def product_variant_updated(
        self, product_variant: "ProductVariant", previous_value: Any
    ) -> Any:
        if not self.active:
            return previous_value
        product_variant_data = generate_product_variant_payload([product_variant])
        trigger_webhooks_for_event.delay(
            WebhookEventType.PRODUCT_VARIANT_UPDATED, product_variant_data
        )

    def product_variant_deleted(
        self, product_variant: "ProductVariant", previous_value: Any
    ) -> Any:
        if not self.active:
            return previous_value
        product_variant_data = generate_product_variant_payload([product_variant])
        trigger_webhooks_for_event.delay(
            WebhookEventType.PRODUCT_VARIANT_DELETED, product_variant_data
        )

    def product_variant_out_of_stock(self, stock: "Stock", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        product_variant_data = generate_product_variant_with_stock_payload([stock])
        trigger_webhooks_for_event.delay(
            WebhookEventType.PRODUCT_VARIANT_OUT_OF_STOCK, product_variant_data
        )

    def product_variant_back_in_stock(self, stock: "Stock", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        product_variant_data = generate_product_variant_with_stock_payload([stock])
        trigger_webhooks_for_event.delay(
            WebhookEventType.PRODUCT_VARIANT_BACK_IN_STOCK, product_variant_data
        )

    def checkout_created(self, checkout: "Checkout", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        checkout_data = generate_checkout_payload(checkout)
        trigger_webhooks_for_event.delay(
            WebhookEventType.CHECKOUT_CREATED, checkout_data
        )

    def checkout_updated(self, checkout: "Checkout", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        checkout_data = generate_checkout_payload(checkout)
        trigger_webhooks_for_event.delay(
            WebhookEventType.CHECKOUT_UPDATED, checkout_data
        )

    def notify(
        self, event: Union[NotifyEventType, str], payload: dict, previous_value
    ) -> Any:
        if not self.active:
            return previous_value

        notify_user_event = WebhookEventType.NOTIFY_USER
        data = {"notify_event": event, "payload": payload}

        if event not in NotifyEventType.CHOICES:
            logger.info(
                f"Webhook {notify_user_event} triggered for {event} notify event."
            )

        trigger_webhooks_for_event.delay(
            notify_user_event, json.dumps(data, cls=CustomJsonEncoder)
        )

    def page_created(self, page: "Page", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        page_data = generate_page_payload(page)
        trigger_webhooks_for_event.delay(WebhookEventType.PAGE_CREATED, page_data)

    def page_updated(self, page: "Page", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        page_data = generate_page_payload(page)
        trigger_webhooks_for_event.delay(WebhookEventType.PAGE_UPDATED, page_data)

    def page_deleted(self, page: "Page", previous_value: Any) -> Any:
        if not self.active:
            return previous_value
        page_data = generate_page_payload(page)
        trigger_webhooks_for_event.delay(WebhookEventType.PAGE_DELETED, page_data)

    def translation_created(self, translation: "Translation", previous_value: Any):
        if not self.active:
            return previous_value
        translation_data = generate_translation_payload(translation)
        trigger_webhooks_for_event.delay(
            WebhookEventType.TRANSLATION_CREATED, translation_data
        )

    def translation_updated(self, translation: "Translation", previous_value: Any):
        if not self.active:
            return previous_value
        translation_data = generate_translation_payload(translation)
        trigger_webhooks_for_event.delay(
            WebhookEventType.TRANSLATION_UPDATED, translation_data
        )

    def __run_payment_webhook(
        self,
        event_type: str,
        transaction_kind: str,
        payment_information: "PaymentData",
        previous_value,
        **kwargs
    ) -> "GatewayResponse":
        if not self.active:
            return previous_value

        app = None
        payment_app_data = from_payment_app_id(payment_information.gateway)

        if payment_app_data is not None:
            app = (
                App.objects.for_event_type(event_type)
                .filter(pk=payment_app_data.app_pk)
                .first()
            )

        if not app:
            logger.warning(
                "Payment webhook for event %r failed - no active app found: %r",
                event_type,
                payment_information.gateway,
            )
            raise PaymentError(
                f"Payment method {payment_information.gateway} is not available: "
                "app not found."
            )

        webhook_payload = generate_payment_payload(payment_information)
        response_data = trigger_webhook_sync(event_type, webhook_payload, app)
        if response_data is None:
            raise PaymentError(
                f"Payment method {payment_information.gateway} is not available: "
                "no response from the app."
            )

        return parse_payment_action_response(
            payment_information, response_data, transaction_kind
        )

    def token_is_required_as_payment_input(self, previous_value):
        return False

    def get_payment_gateways(
        self,
        currency: Optional[str],
        checkout: Optional["Checkout"],
        previous_value,
        **kwargs
    ) -> List["PaymentGateway"]:
        gateways = []
        apps = App.objects.for_event_type(
            WebhookEventType.PAYMENT_LIST_GATEWAYS
        ).prefetch_related("webhooks")
        for app in apps:
            response_data = trigger_webhook_sync(
                event_type=WebhookEventType.PAYMENT_LIST_GATEWAYS,
                data=generate_list_gateways_payload(currency, checkout),
                app=app,
            )
            if response_data:
                app_gateways = parse_list_payment_gateways_response(response_data, app)
                if currency:
                    app_gateways = [
                        gtw for gtw in app_gateways if currency in gtw.currencies
                    ]
                gateways.extend(app_gateways)
        return gateways

    def authorize_payment(
        self, payment_information: "PaymentData", previous_value, **kwargs
    ) -> "GatewayResponse":
        return self.__run_payment_webhook(
            WebhookEventType.PAYMENT_AUTHORIZE,
            TransactionKind.AUTH,
            payment_information,
            previous_value,
            **kwargs,
        )

    def capture_payment(
        self, payment_information: "PaymentData", previous_value, **kwargs
    ) -> "GatewayResponse":
        return self.__run_payment_webhook(
            WebhookEventType.PAYMENT_CAPTURE,
            TransactionKind.CAPTURE,
            payment_information,
            previous_value,
            **kwargs,
        )

    def refund_payment(
        self, payment_information: "PaymentData", previous_value, **kwargs
    ) -> "GatewayResponse":
        return self.__run_payment_webhook(
            WebhookEventType.PAYMENT_REFUND,
            TransactionKind.REFUND,
            payment_information,
            previous_value,
            **kwargs,
        )

    def void_payment(
        self, payment_information: "PaymentData", previous_value, **kwargs
    ) -> "GatewayResponse":
        return self.__run_payment_webhook(
            WebhookEventType.PAYMENT_VOID,
            TransactionKind.VOID,
            payment_information,
            previous_value,
            **kwargs,
        )

    def confirm_payment(
        self, payment_information: "PaymentData", previous_value, **kwargs
    ) -> "GatewayResponse":
        return self.__run_payment_webhook(
            WebhookEventType.PAYMENT_CONFIRM,
            TransactionKind.CONFIRM,
            payment_information,
            previous_value,
            **kwargs,
        )

    def process_payment(
        self, payment_information: "PaymentData", previous_value, **kwargs
    ) -> "GatewayResponse":
        return self.__run_payment_webhook(
            WebhookEventType.PAYMENT_PROCESS,
            TransactionKind.CAPTURE,
            payment_information,
            previous_value,
            **kwargs,
        )

    def get_shipping_methods_for_checkout(
        self, checkout: "Checkout", previous_value: Any
    ) -> List["ShippingMethodData"]:
        methods = []
        apps = App.objects.for_event_type(
            WebhookEventType.SHIPPING_LIST_METHODS_FOR_CHECKOUT
        ).prefetch_related("webhooks")
        payload = generate_checkout_payload(checkout)
        for app in apps:
            response_data = trigger_webhook_sync(
                event_type=WebhookEventType.SHIPPING_LIST_METHODS_FOR_CHECKOUT,
                data=payload,
                app=app,
            )
            if response_data:
                shipping_methods = parse_list_shipping_methods_response(
                    response_data, app
                )
                methods.extend(shipping_methods)
        return methods
