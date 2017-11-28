from __future__ import unicode_literals

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.context_processors import csrf
from django.template.response import TemplateResponse
from django.utils.translation import pgettext_lazy
from django_prices.templatetags.prices_i18n import gross
from payments import PaymentStatus
from prices import Price

from .forms import (
    CancelGroupForm, CancelLinesForm, CancelOrderForm, CapturePaymentForm,
    ChangeStockForm, ChangeQuantityForm, MoveLinesForm, OrderNoteForm,
    RefundPaymentForm, ReleasePaymentForm, RemoveVoucherForm, ShipGroupForm)
from .utils import (create_packing_slip_pdf, create_invoice_pdf,
                    get_statics_absolute_url)
from ..order.forms import OrderFilterForm
from ..views import staff_member_required
from ...core.utils import get_paginator_items
from ...order import OrderStatus
from ...order.models import Order, OrderLine, OrderNote
from ...product.models import ProductVariant
from ...settings import DASHBOARD_PAGINATE_BY
from ...userprofile.i18n import AddressForm


@staff_member_required
@permission_required('order.view_order')
def order_list(request):
    orders_all = Order.objects.prefetch_related(
        'groups', 'payments', 'groups__items', 'user')
    status = request.GET.get('status')
    if status:
        orders = orders_all.filter(status=status)
    else:
        orders = orders_all.all()
    orders = get_paginator_items(
        orders, DASHBOARD_PAGINATE_BY, request.GET.get('page'))
    form = OrderFilterForm(
        request.POST or None, initial={'status': status or None})
    ctx = {'orders': orders,
           'form': form}
    return TemplateResponse(request, 'dashboard/order/list.html', ctx)


@staff_member_required
@permission_required('order.view_order')
def order_details(request, order_pk):
    qs = (Order.objects
          .select_related('user', 'shipping_address', 'billing_address')
          .prefetch_related('notes', 'payments', 'history',
                            'groups', 'groups__items'))
    order = get_object_or_404(qs, pk=order_pk)
    notes = order.notes.all()
    all_payments = order.payments.exclude(status=PaymentStatus.INPUT)
    payment = order.payments.last()
    groups = list(order)
    captured = preauthorized = Price(0, currency=order.get_total().currency)
    balance = captured - order.get_total()
    if payment:
        can_capture = (
            payment.status == PaymentStatus.PREAUTH and
            order.status != OrderStatus.CANCELLED)
        can_release = payment.status == PaymentStatus.PREAUTH
        can_refund = payment.status == PaymentStatus.CONFIRMED
        preauthorized = payment.get_total_price()
        if payment.status == PaymentStatus.CONFIRMED:
            captured = payment.get_captured_price()
            balance = captured - order.get_total()
    else:
        can_capture = can_release = can_refund = False

    ctx = {'order': order, 'all_payments': all_payments, 'payment': payment,
           'notes': notes, 'groups': groups, 'captured': captured,
           'preauthorized': preauthorized, 'can_capture': can_capture,
           'can_release': can_release, 'can_refund': can_refund,
           'balance': balance}
    return TemplateResponse(request, 'dashboard/order/detail.html', ctx)


@staff_member_required
@permission_required('order.edit_order')
def order_add_note(request, order_pk):
    order = get_object_or_404(Order, pk=order_pk)
    note = OrderNote(order=order, user=request.user)
    form = OrderNoteForm(request.POST or None, instance=note)
    status = 200
    if form.is_valid():
        form.save()
        msg = pgettext_lazy(
            'Dashboard message related to an order',
            'Added note')
        order.create_history_entry(comment=msg, user=request.user)
        messages.success(request, msg)
    elif form.errors:
        status = 400
    ctx = {'order': order, 'form': form}
    ctx.update(csrf(request))
    template = 'dashboard/order/modal/add_note.html'
    return TemplateResponse(request, template, ctx, status=status)


@staff_member_required
@permission_required('order.edit_order')
def capture_payment(request, order_pk, payment_pk):
    order = get_object_or_404(Order, pk=order_pk)
    payment = get_object_or_404(order.payments, pk=payment_pk)
    amount = order.get_total().quantize('0.01').gross
    form = CapturePaymentForm(request.POST or None, payment=payment,
                              initial={'amount': amount})
    if form.is_valid() and form.capture():
        amount = form.cleaned_data['amount']
        msg = pgettext_lazy(
            'Dashboard message related to a payment',
            'Captured %(amount)s') % {'amount': gross(amount)}
        payment.order.create_history_entry(comment=msg, user=request.user)
        messages.success(request, msg)
        return redirect('dashboard:order-details', order_pk=order.pk)
    status = 400 if form.errors else 200
    ctx = {'captured': payment.captured_amount, 'currency': payment.currency,
           'form': form, 'order': order, 'payment': payment}
    return TemplateResponse(request, 'dashboard/order/modal/capture.html', ctx,
                            status=status)


@staff_member_required
@permission_required('order.edit_order')
def refund_payment(request, order_pk, payment_pk):
    order = get_object_or_404(Order, pk=order_pk)
    payment = get_object_or_404(order.payments, pk=payment_pk)
    amount = payment.captured_amount
    form = RefundPaymentForm(request.POST or None, payment=payment,
                             initial={'amount': amount})
    if form.is_valid() and form.refund():
        amount = form.cleaned_data['amount']
        msg = pgettext_lazy(
            'Dashboard message related to a payment',
            'Refunded %(amount)s') % {'amount': gross(amount)}
        payment.order.create_history_entry(comment=msg, user=request.user)
        messages.success(request, msg)
        return redirect('dashboard:order-details', order_pk=order.pk)
    status = 400 if form.errors else 200
    ctx = {'captured': payment.captured_amount, 'currency': payment.currency,
           'form': form, 'order': order, 'payment': payment}
    return TemplateResponse(request, 'dashboard/order/modal/refund.html', ctx,
                            status=status)


@staff_member_required
@permission_required('order.edit_order')
def release_payment(request, order_pk, payment_pk):
    order = get_object_or_404(Order, pk=order_pk)
    payment = get_object_or_404(order.payments, pk=payment_pk)
    form = ReleasePaymentForm(request.POST or None, payment=payment)
    if form.is_valid() and form.release():
        msg = pgettext_lazy('Dashboard message', 'Released payment')
        payment.order.create_history_entry(comment=msg, user=request.user)
        messages.success(request, msg)
        return redirect('dashboard:order-details', order_pk=order.pk)
    status = 400 if form.errors else 200
    ctx = {'captured': payment.captured_amount, 'currency': payment.currency,
           'form': form, 'order': order, 'payment': payment}
    return TemplateResponse(request, 'dashboard/order/modal/release.html', ctx,
                            status=status)


@staff_member_required
@permission_required('order.edit_order')
def orderline_change_quantity(request, order_pk, line_pk):
    order = get_object_or_404(Order, pk=order_pk)
    line = get_object_or_404(OrderLine.objects.filter(
        delivery_group__order=order), pk=line_pk)
    form = ChangeQuantityForm(request.POST or None, instance=line)
    status = 200
    old_quantity = line.quantity
    if form.is_valid():
        with transaction.atomic():
            form.save()
        msg = pgettext_lazy(
            'Dashboard message related to an order line',
            'Changed quantity for product %(product)s from'
            ' %(old_quantity)s to %(new_quantity)s') % {
                'product': line.product, 'old_quantity': old_quantity,
                'new_quantity': line.quantity}
        order.create_history_entry(comment=msg, user=request.user)
        messages.success(request, msg)
        return redirect('dashboard:order-details', order_pk=order.pk)
    elif form.errors:
        status = 400
    ctx = {'order': order, 'object': line, 'form': form}
    template = 'dashboard/order/modal/change_quantity.html'
    return TemplateResponse(request, template, ctx, status=status)


@staff_member_required
@permission_required('order.edit_order')
def orderline_split(request, order_pk, line_pk):
    order = get_object_or_404(Order, pk=order_pk)
    line = get_object_or_404(OrderLine.objects.filter(
        delivery_group__order=order), pk=line_pk)
    form = MoveLinesForm(request.POST or None, line=line)
    line_pk = None
    if line:
        line_pk = line.pk
    status = 200
    if form.is_valid():
        old_group = line.delivery_group
        how_many = form.cleaned_data['quantity']
        with transaction.atomic():
            target_group = form.move_lines()
        if not old_group.pk:
            old_group = pgettext_lazy(
                'Dashboard message related to a delivery group',
                'removed group')
        msg = pgettext_lazy(
            'Dashboard message related to delivery groups',
            'Moved %(how_many)s items %(item)s from %(old_group)s'
            ' to %(new_group)s') % {
                'how_many': how_many, 'item': line, 'old_group': old_group,
                'new_group': target_group}
        order.create_history_entry(comment=msg, user=request.user)
        messages.success(request, msg)
        return redirect('dashboard:order-details', order_pk=order.pk)
    elif form.errors:
        status = 400
    ctx = {'order': order, 'object': line, 'form': form, 'line_pk': line_pk}
    template = 'dashboard/order/modal/split_order_line.html'
    return TemplateResponse(request, template, ctx, status=status)


@staff_member_required
@permission_required('order.edit_order')
def orderline_cancel(request, order_pk, line_pk):
    order = get_object_or_404(Order, pk=order_pk)
    line = get_object_or_404(OrderLine.objects.filter(
        delivery_group__order=order), pk=line_pk)
    form = CancelLinesForm(data=request.POST or None, line=line)
    status = 200
    if form.is_valid():
        msg = pgettext_lazy(
            'Dashboard message related to an order line',
            'Cancelled item %s') % line
        with transaction.atomic():
            form.cancel_line()
            order.create_history_entry(comment=msg, user=request.user)
            messages.success(request, msg)
        return redirect('dashboard:order-details', order_pk=order.pk)
    elif form.errors:
        status = 400
    ctx = {'order': order, 'item': line, 'form': form}
    return TemplateResponse(
        request, 'dashboard/order/modal/cancel_line.html',
        ctx, status=status)


@staff_member_required
@permission_required('order.edit_order')
def ship_delivery_group(request, order_pk, group_pk):
    order = get_object_or_404(Order, pk=order_pk)
    group = get_object_or_404(order.groups.all(), pk=group_pk)
    form = ShipGroupForm(request.POST or None, instance=group)
    status = 200
    if form.is_valid():
        with transaction.atomic():
            form.save()
        msg = pgettext_lazy(
            'Dashboard message related to a delivery group',
            'Shipped %s') % group
        messages.success(request, msg)
        group.order.create_history_entry(comment=msg, user=request.user)
        return redirect('dashboard:order-details', order_pk=order_pk)
    elif form.errors:
        status = 400
    ctx = {'order': order, 'group': group, 'form': form}
    template = 'dashboard/order/modal/ship_delivery_group.html'
    return TemplateResponse(request, template, ctx, status=status)


@staff_member_required
@permission_required('order.edit_order')
def cancel_delivery_group(request, order_pk, group_pk):
    order = get_object_or_404(Order, pk=order_pk)
    group = get_object_or_404(order.groups.all(), pk=group_pk)
    form = CancelGroupForm(request.POST or None, delivery_group=group)
    status = 200
    if form.is_valid():
        with transaction.atomic():
            form.cancel_group()
        msg = pgettext_lazy(
            'Dashboard message related to a delivery group',
            'Cancelled %s') % group
        messages.success(request, msg)
        group.order.create_history_entry(comment=msg, user=request.user)
        return redirect('dashboard:order-details', order_pk=order_pk)
    elif form.errors:
        status = 400
    ctx = {'order': order, 'group': group}
    template = 'dashboard/order/modal/cancel_delivery_group.html'
    return TemplateResponse(request, template, ctx, status=status)


@staff_member_required
@permission_required('order.edit_order')
def address_view(request, order_pk, address_type):
    order = Order.objects.get(pk=order_pk)
    if address_type == 'shipping':
        address = order.shipping_address
        success_msg = pgettext_lazy(
            'Dashboard message',
            'Updated shipping address')
    else:
        address = order.billing_address
        success_msg = pgettext_lazy(
            'Dashboard message',
            'Updated billing address')
    form = AddressForm(request.POST or None, instance=address)
    if form.is_valid():
        form.save()
        order.create_history_entry(comment=success_msg, user=request.user)
        messages.success(request, success_msg)
        return redirect('dashboard:order-details', order_pk=order_pk)
    ctx = {'order': order, 'address_type': address_type, 'form': form}
    return TemplateResponse(request, 'dashboard/order/address_form.html', ctx)


@staff_member_required
@permission_required('order.edit_order')
def cancel_order(request, order_pk):
    status = 200
    order = get_object_or_404(Order, pk=order_pk)
    form = CancelOrderForm(request.POST or None, order=order)
    if form.is_valid():
        msg = pgettext_lazy('Dashboard message', 'Cancelled order')
        with transaction.atomic():
            form.cancel_order()
            order.create_history_entry(comment=msg, user=request.user)
        messages.success(request, 'Order cancelled')
        return redirect('dashboard:order-details', order_pk=order.pk)
        # TODO: send status confirmation email
    elif form.errors:
        status = 400
    ctx = {'order': order}
    return TemplateResponse(request, 'dashboard/order/modal/cancel_order.html',
                            ctx, status=status)


@staff_member_required
@permission_required('order.edit_order')
def remove_order_voucher(request, order_pk):
    status = 200
    order = get_object_or_404(Order, pk=order_pk)
    form = RemoveVoucherForm(request.POST or None, order=order)
    if form.is_valid():
        msg = pgettext_lazy('Dashboard message', 'Removed voucher from order')
        with transaction.atomic():
            form.remove_voucher()
            order.create_history_entry(comment=msg, user=request.user)
        messages.success(request, msg)
        return redirect('dashboard:order-details', order_pk=order.pk)
    elif form.errors:
        status = 400
    ctx = {'order': order}
    return TemplateResponse(request,
                            'dashboard/order/modal/order_remove_voucher.html',
                            ctx, status=status)


@staff_member_required
@permission_required('order.edit_order')
def order_invoice(request, order_pk):
    absolute_url = get_statics_absolute_url(request)
    pdf_file, order = create_invoice_pdf(order_pk, absolute_url)
    response = HttpResponse(pdf_file, content_type='application/pdf')
    name = "invoice-%s" % order.id
    response['Content-Disposition'] = 'filename=%s' % name
    return response


@staff_member_required
@permission_required('order.edit_order')
def order_packing_slip(request, group_pk):
    absolute_url = get_statics_absolute_url(request)
    pdf_file, group = create_packing_slip_pdf(group_pk, absolute_url)
    response = HttpResponse(pdf_file, content_type='application/pdf')
    name = "packing-slip-%s-%s" % (group.order.id, group.id)
    response['Content-Disposition'] = 'filename=%s' % name
    return response


@staff_member_required
@permission_required('order.edit_order')
def orderline_change_stock(request, order_pk, line_pk):
    line = get_object_or_404(OrderLine, pk=line_pk)
    status = 200
    form = ChangeStockForm(request.POST or None, instance=line)
    if form.is_valid():
        form.save()
        msg = pgettext_lazy(
            'Dashboard message',
            'Stock location changed for %s') % form.instance.product_sku
        messages.success(request, msg)
    elif form.errors:
        status = 400
    ctx = {'order_pk': order_pk, 'line_pk': line_pk, 'form': form}
    template = 'dashboard/order/modal/delivery_group_stock.html'
    return TemplateResponse(request, template, ctx, status=status)
