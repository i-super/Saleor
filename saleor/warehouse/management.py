from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import F, Sum

from ..core.exceptions import InsufficientStock
from .models import Allocation, Stock, Warehouse

if TYPE_CHECKING:
    from ..order.models import OrderLine
    from ..product.models import ProductVariant


@transaction.atomic
def allocate_stock(
    order_line: "OrderLine", country_code: str, quantity: int,
):
    """Allocate stocks for given `order_line` in given country.

    Function lock for update all stocks and allocations for variant in
    given country and order by pk. Next, generate the dictionary
    ({"stock_pk": "quantity_allocated"}) with actual allocated quantity for stocks.
    Iterate by stocks and allocate as many items as needed or available in stock
    for order line, until allocated all required quantity for the order line.
    If there is less quantity in stocks then rise InsufficientStock exception.
    """
    stocks = (
        Stock.objects.select_for_update(of=("self",))
        .get_variant_stocks_for_country(country_code, order_line.variant)
        .order_by("pk")
    )

    quantity_allocation_list = list(
        Allocation.objects.filter(stock__in=stocks, quantity_allocated__gt=0,)
        .values("stock")
        .annotate(Sum("quantity_allocated"))
    )
    quantity_allocation_for_stocks = {
        allocation["stock"]: allocation["quantity_allocated__sum"]
        for allocation in quantity_allocation_list
    }

    quantity_allocated = 0
    allocations = []

    for stock in stocks:
        quantity_allocated_in_stock = quantity_allocation_for_stocks.get(stock.pk, 0)

        quantity_available_in_stock = stock.quantity - quantity_allocated_in_stock

        quantity_to_allocate = min(
            (quantity - quantity_allocated), quantity_available_in_stock
        )
        if quantity_to_allocate > 0:
            allocations.append(
                Allocation(
                    order_line=order_line,
                    stock=stock,
                    quantity_allocated=quantity_to_allocate,
                )
            )

            quantity_allocated += quantity_to_allocate
            if quantity_allocated == quantity:
                Allocation.objects.bulk_create(allocations)
                return None
    raise InsufficientStock(order_line.variant)


@transaction.atomic
def deallocate_stock(order_line: "OrderLine", quantity: int):
    """Deallocate stocks for given `order_line`.

    Function lock for update stocks and allocations related to given `order_line`.
    Iterate over allocations sorted by `stock.pk` and deallocate as many items
    as needed of available in stock for order line, until deallocated all required
    quantity for the order line. If there is less quantity in stocks then
    raise an exception.
    """
    allocations = (
        order_line.allocations.select_related("stock")
        .select_for_update(of=("self", "stock",))
        .order_by("stock__pk")
    )
    quantity_dealocated = 0
    for allocation in allocations:
        quantity_to_deallocate = min(
            (quantity - quantity_dealocated), allocation.quantity_allocated
        )
        if quantity_to_deallocate > 0:
            allocation.quantity_allocated = (
                F("quantity_allocated") - quantity_to_deallocate
            )
            quantity_dealocated += quantity_to_deallocate
            if quantity_dealocated == quantity:
                Allocation.objects.bulk_update(allocations, ["quantity_allocated"])
                return None
    raise Exception(
        f"Can't deallocate {quantity} for variant: {order_line.variant}"
        f" in order: {order_line.order}"
    )


@transaction.atomic
def increase_stock(
    order_line: "OrderLine",
    warehouse: Warehouse,
    quantity: int,
    allocate: bool = False,
):
    """Increse stock quantity for given `order_line` in a given warehouse.

    Function lock for update stock and allocations related to given `order_line`
    in a given warehouse. If the stock exists, increase the stock quantity
    by given value. If not exist create a stock with the given quantity. This function
    can create the allocation for increased quantity in stock by passing True
    to `allocate` argument. If the order line has the allocation in this stock
    function increase `quantity_allocated`. If allocation does not exist function
    create a new allocation for this order line in this stock.
    """
    stock = (
        Stock.objects.select_for_update(of=("self",))
        .filter(warehouse=warehouse, product_variant=order_line.variant)
        .first()
    )
    if stock:
        stock.increase_stock(quantity, commit=True)
    else:
        stock = Stock.objects.create(
            warehouse=warehouse, product_variant=order_line.variant, quantity=quantity
        )
    if allocate:
        allocation = order_line.allocations.filter(stock=stock).first()
        if allocation:
            allocation.quantity_allocated = F("quantity_allocated") + quantity
            allocation.save(update_fields=["quantity_allocated"])
        else:
            Allocation.objects.create(
                order_line=order_line, stock=stock, quantity_allocated=quantity
            )


@transaction.atomic
def decrease_stock(order_line: "OrderLine", quantity: int):
    """Decrease stock quantity for given `order_line`.

    Function lock for update stocks and allocations related to given `order_line`.
    Iterate over allocations sorted by `stock.pk` and deallocate and decrease stock
    quantity for as many items as needed of available in stock for order line, until
    deallocated all required quantity for the order line. If there is less quantity in
    stocks then raise an exception.
    """
    allocations = (
        order_line.allocations.select_related("stock")
        .select_for_update(of=("self", "stock",))
        .order_by("stock__pk")
    )
    quantity_decreased = 0
    updated_stocks = []

    for allocation in allocations:
        quantity_to_decreased = min(
            (quantity - quantity_decreased), allocation.quantity_allocated
        )
        if quantity_to_decreased > 0:

            allocation.quantity_allocated = (
                F("quantity_allocated") - quantity_to_decreased
            )

            stock = allocation.stock
            stock.quantity = F("quantity") - quantity_to_decreased
            updated_stocks.append(stock)

            quantity_decreased += quantity_to_decreased
            if quantity_decreased == quantity:
                Allocation.objects.bulk_update(allocations, ["quantity_allocated"])
                Stock.objects.bulk_update(updated_stocks, ["quantity"])
                return None
    raise Exception(
        f"Can't decrease {quantity} for variant: {order_line.variant}"
        f" in order: {order_line.order}"
    )


@transaction.atomic
def set_stock_quantity(
    variant: "ProductVariant", country_code: str, quantity: int
) -> Stock:
    stock = (
        Stock.objects.select_for_update(of=("self",))
        .get_variant_stocks_for_country(country_code, variant)
        .order_by("pk")
        .first()
    )
    if stock:
        stock.quantity = quantity
        stock.save(update_fields=["quantity"])
    else:
        warehouse = Warehouse.objects.for_country(country_code).first()
        stock = Stock.objects.create(
            warehouse=warehouse, product_variant=variant, quantity=quantity
        )
    return stock
