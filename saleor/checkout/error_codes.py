from enum import Enum


class CheckoutErrorCode(Enum):
    BILLING_ADDRESS_NOT_SET = "billing_address_not_set"
    CHECKOUT_NOT_FULLY_PAID = "checkout_not_fully_paid"
    GRAPHQL_ERROR = "graphql_error"
    PRODUCT_NOT_PUBLISHED = "product_not_published"
    INSUFFICIENT_STOCK = "insufficient_stock"
    INVALID = "invalid"
    INVALID_SHIPPING_METHOD = "invalid_shipping_method"
    NOT_FOUND = "not_found"
    PAYMENT_ERROR = "payment_error"
    QUANTITY_GREATER_THAN_LIMIT = "quantity_greater_than_limit"
    REQUIRED = "required"
    SHIPPING_ADDRESS_NOT_SET = "shipping_address_not_set"
    SHIPPING_METHOD_NOT_APPLICABLE = "shipping_method_not_applicable"
    SHIPPING_METHOD_NOT_SET = "shipping_method_not_set"
    SHIPPING_NOT_REQUIRED = "shipping_not_required"
    TAX_ERROR = "tax_error"
    UNIQUE = "unique"
    VOUCHER_NOT_APPLICABLE = "voucher_not_applicable"
    ZERO_QUANTITY = "zero_quantity"
