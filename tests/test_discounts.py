from datetime import timedelta

import pytest
from django.utils import timezone
from prices import Money

from saleor.checkout.utils import get_voucher_discount_for_checkout
from saleor.discount import DiscountInfo, DiscountValueType, VoucherType
from saleor.discount.models import NotApplicable, Sale, Voucher
from saleor.discount.utils import (
    decrease_voucher_usage,
    get_product_discount_on_sale,
    get_products_voucher_discount,
    get_shipping_voucher_discount,
    get_value_voucher_discount,
    increase_voucher_usage,
)
from saleor.product.models import Product, ProductVariant


def get_min_amount_spent(min_amount_spent):
    if min_amount_spent is not None:
        return Money(min_amount_spent, "USD")
    return None


@pytest.mark.parametrize(
    "min_amount_spent, value",
    [(Money(5, "USD"), Money(10, "USD")), (Money(10, "USD"), Money(10, "USD"))],
)
def test_valid_voucher_min_amount_spent(min_amount_spent, value):
    voucher = Voucher(
        code="unique",
        type=VoucherType.SHIPPING,
        discount_value_type=DiscountValueType.FIXED,
        discount_value=Money(10, "USD"),
        min_amount_spent=min_amount_spent,
    )
    voucher.validate_min_amount_spent(value)


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_variant_discounts(product):
    variant = product.variants.get()
    low_sale = Sale(type=DiscountValueType.FIXED, value=5)
    low_discount = DiscountInfo(
        sale=low_sale,
        product_ids={product.id},
        category_ids=set(),
        collection_ids=set(),
    )
    sale = Sale(type=DiscountValueType.FIXED, value=8)
    discount = DiscountInfo(
        sale=sale, product_ids={product.id}, category_ids=set(), collection_ids=set()
    )
    high_sale = Sale(type=DiscountValueType.FIXED, value=50)
    high_discount = DiscountInfo(
        sale=high_sale,
        product_ids={product.id},
        category_ids=set(),
        collection_ids=set(),
    )
    final_price = variant.get_price(discounts=[low_discount, discount, high_discount])
    assert final_price == Money(0, "USD")


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_percentage_discounts(product):
    variant = product.variants.get()
    sale = Sale(type=DiscountValueType.PERCENTAGE, value=50)
    discount = DiscountInfo(
        sale=sale, product_ids={product.id}, category_ids=set(), collection_ids={}
    )
    final_price = variant.get_price(discounts=[discount])
    assert final_price == Money(5, "USD")


def test_voucher_queryset_active(voucher):
    vouchers = Voucher.objects.all()
    assert len(vouchers) == 1
    active_vouchers = Voucher.objects.active(date=timezone.now() - timedelta(days=1))
    assert len(active_vouchers) == 0


@pytest.mark.parametrize(
    "prices, discount_value, discount_type, apply_once_per_order, expected_value",
    [
        ([10], 10, DiscountValueType.FIXED, True, 10),
        ([5], 10, DiscountValueType.FIXED, True, 5),
        ([5, 5], 10, DiscountValueType.FIXED, True, 5),
        ([2, 3], 10, DiscountValueType.FIXED, True, 2),
        ([10, 10], 5, DiscountValueType.FIXED, False, 10),
        ([5, 2], 5, DiscountValueType.FIXED, False, 7),
        ([10, 10, 10], 5, DiscountValueType.FIXED, False, 15),
    ],
)
def test_products_voucher_checkout_discount_not(
    monkeypatch,
    prices,
    discount_value,
    discount_type,
    expected_value,
    apply_once_per_order,
    checkout_with_item,
):
    monkeypatch.setattr(
        "saleor.checkout.utils.get_prices_of_discounted_products",
        lambda lines, discounted_products: (Money(price, "USD") for price in prices),
    )
    voucher = Voucher(
        code="unique",
        type=VoucherType.PRODUCT,
        discount_value_type=discount_type,
        discount_value=discount_value,
        apply_once_per_order=apply_once_per_order,
    )
    voucher.save()
    checkout = checkout_with_item
    discount = get_voucher_discount_for_checkout(voucher, checkout)
    assert discount == Money(expected_value, "USD")


def test_sale_applies_to_correct_products(product_type, category):
    product = Product.objects.create(
        name="Test Product",
        price=Money(10, "USD"),
        description="",
        pk=111,
        product_type=product_type,
        category=category,
    )
    variant = ProductVariant.objects.create(product=product, sku="firstvar")
    product2 = Product.objects.create(
        name="Second product",
        price=Money(15, "USD"),
        description="",
        product_type=product_type,
        category=category,
    )
    sec_variant = ProductVariant.objects.create(product=product2, sku="secvar", pk=111)
    sale = Sale(name="Test sale", value=3, type=DiscountValueType.FIXED)
    discount = DiscountInfo(
        sale=sale, product_ids={product.id}, category_ids=set(), collection_ids=set()
    )
    product_discount = get_product_discount_on_sale(variant.product, discount)
    discounted_price = product_discount(product.price)
    assert discounted_price == Money(7, "USD")
    with pytest.raises(NotApplicable):
        get_product_discount_on_sale(sec_variant.product, discount)


def test_increase_voucher_usage():
    voucher = Voucher.objects.create(
        code="unique",
        type=VoucherType.ENTIRE_ORDER,
        discount_value_type=DiscountValueType.FIXED,
        discount_value=10,
        usage_limit=100,
    )
    increase_voucher_usage(voucher)
    voucher.refresh_from_db()
    assert voucher.used == 1


def test_decrease_voucher_usage():
    voucher = Voucher.objects.create(
        code="unique",
        type=VoucherType.ENTIRE_ORDER,
        discount_value_type=DiscountValueType.FIXED,
        discount_value=10,
        usage_limit=100,
        used=10,
    )
    decrease_voucher_usage(voucher)
    voucher.refresh_from_db()
    assert voucher.used == 9


@pytest.mark.parametrize(
    "total, min_amount_spent, discount_value, discount_value_type, expected_value",
    [
        (20, 15, 50, DiscountValueType.PERCENTAGE, 10),
        (20, None, 50, DiscountValueType.PERCENTAGE, 10),
        (20, 15, 5, DiscountValueType.FIXED, 5),
        (20, None, 5, DiscountValueType.FIXED, 5),
    ],
)
def test_get_value_voucher_discount(
    total, min_amount_spent, discount_value, discount_value_type, expected_value
):
    voucher = Voucher(
        code="unique",
        type=VoucherType.ENTIRE_ORDER,
        discount_value_type=discount_value_type,
        discount_value=discount_value,
        min_amount_spent=get_min_amount_spent(min_amount_spent),
    )
    voucher.save()
    total_price = Money(total, "USD")
    discount = get_value_voucher_discount(voucher, total_price)
    assert discount == Money(expected_value, "USD")


@pytest.mark.parametrize(
    "total, min_amount_spent, shipping_price, discount_value, "
    "discount_value_type, expected_value",
    [
        (20, 15, 10, 50, DiscountValueType.PERCENTAGE, 5),
        (20, None, 10, 50, DiscountValueType.PERCENTAGE, 5),
        (20, 15, 10, 5, DiscountValueType.FIXED, 5),
        (20, None, 10, 5, DiscountValueType.FIXED, 5),
    ],
)
def test_get_shipping_voucher_discount(
    total,
    min_amount_spent,
    shipping_price,
    discount_value,
    discount_value_type,
    expected_value,
):
    voucher = Voucher(
        code="unique",
        type=VoucherType.ENTIRE_ORDER,
        discount_value_type=discount_value_type,
        discount_value=discount_value,
        min_amount_spent=get_min_amount_spent(min_amount_spent),
    )
    voucher.save()
    total = Money(total, "USD")
    shipping_price = Money(shipping_price, "USD")
    discount = get_shipping_voucher_discount(voucher, total, shipping_price)
    assert discount == Money(expected_value, "USD")


@pytest.mark.parametrize(
    "prices, discount_value_type, discount_value, voucher_type, expected_value",
    [  # noqa
        ([5, 10, 15], DiscountValueType.PERCENTAGE, 10, VoucherType.PRODUCT, 3),
        ([5, 10, 15], DiscountValueType.FIXED, 2, VoucherType.PRODUCT, 6),
        ([5, 10, 15], DiscountValueType.FIXED, 2, VoucherType.COLLECTION, 6),
    ],
)
def test_get_voucher_discount_all_products(
    prices, discount_value_type, discount_value, voucher_type, expected_value
):
    prices = [Money(price, "USD") for price in prices]
    voucher = Voucher(
        code="unique",
        type=voucher_type,
        discount_value_type=discount_value_type,
        discount_value=discount_value,
    )
    voucher.save()
    discount = get_products_voucher_discount(voucher, prices)
    assert discount == Money(expected_value, "USD")


date_time_now = timezone.now()


@pytest.mark.parametrize(
    "current_date, start_date, end_date, is_active",
    (
        (date_time_now, date_time_now, date_time_now + timedelta(days=1), True),
        (
            date_time_now + timedelta(days=1),
            date_time_now,
            date_time_now + timedelta(days=1),
            True,
        ),
        (
            date_time_now + timedelta(days=2),
            date_time_now,
            date_time_now + timedelta(days=1),
            False,
        ),
        (
            date_time_now - timedelta(days=2),
            date_time_now,
            date_time_now + timedelta(days=1),
            False,
        ),
        (date_time_now, date_time_now, None, True),
        (date_time_now + timedelta(weeks=10), date_time_now, None, True),
    ),
)
def test_sale_active(current_date, start_date, end_date, is_active):
    Sale.objects.create(
        type=DiscountValueType.FIXED, value=5, start_date=start_date, end_date=end_date
    )
    sale_is_active = Sale.objects.active(date=current_date).exists()
    assert is_active == sale_is_active
