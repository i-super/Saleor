from django.utils.translation import pgettext_lazy

from ..core.permissions import AccountPermissions, OrderPermissions, ProductPermissions


class WebhookEventType:
    ANY = "any_events"
    ORDER_CREATED = "order_created"
    ORDER_FULLY_PAID = "order_fully_paid"
    ORDER_UPDATED = "order_updated"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_FULFILLED = "order_fulfilled"

    CUSTOMER_CREATED = "customer_created"

    PRODUCT_CREATED = "product_created"

    DISPLAY_LABELS = {
        ANY: "Any events",
        ORDER_CREATED: "Order created",
        ORDER_FULLY_PAID: "Order paid",
        ORDER_UPDATED: "Order updated",
        ORDER_CANCELLED: "Order cancelled",
        ORDER_FULFILLED: "Order fulfilled",
        CUSTOMER_CREATED: "Customer created",
        PRODUCT_CREATED: "Product created",
    }

    CHOICES = [
        (ANY, pgettext_lazy("Any events", DISPLAY_LABELS[ANY])),
        (
            ORDER_CREATED,
            pgettext_lazy("Order has been placed", DISPLAY_LABELS[ORDER_CREATED]),
        ),
        (
            ORDER_FULLY_PAID,
            pgettext_lazy(
                "Order has been fully paid", DISPLAY_LABELS[ORDER_FULLY_PAID]
            ),
        ),
        (
            ORDER_UPDATED,
            pgettext_lazy("Order has been updated", DISPLAY_LABELS[ORDER_UPDATED]),
        ),
        (
            ORDER_CANCELLED,
            pgettext_lazy("Order has been cancelled", DISPLAY_LABELS[ORDER_CANCELLED]),
        ),
        (
            ORDER_FULFILLED,
            pgettext_lazy("Order has been fulfilled", DISPLAY_LABELS[ORDER_FULFILLED]),
        ),
        (
            CUSTOMER_CREATED,
            pgettext_lazy(
                "Customer has been created", DISPLAY_LABELS[CUSTOMER_CREATED]
            ),
        ),
        (
            PRODUCT_CREATED,
            pgettext_lazy("Product has been created", DISPLAY_LABELS[PRODUCT_CREATED]),
        ),
    ]

    PERMISSIONS = {
        ORDER_CREATED: OrderPermissions.MANAGE_ORDERS,
        ORDER_FULLY_PAID: OrderPermissions.MANAGE_ORDERS,
        ORDER_UPDATED: OrderPermissions.MANAGE_ORDERS,
        ORDER_CANCELLED: OrderPermissions.MANAGE_ORDERS,
        ORDER_FULFILLED: OrderPermissions.MANAGE_ORDERS,
        CUSTOMER_CREATED: AccountPermissions.MANAGE_USERS,
        PRODUCT_CREATED: ProductPermissions.MANAGE_PRODUCTS,
    }
