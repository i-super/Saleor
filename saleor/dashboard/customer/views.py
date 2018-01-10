from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils.translation import pgettext_lazy

from ...core.utils import get_paginator_items
from ...userprofile.models import User
from ..views import staff_member_required
from ..emails import send_set_password_email
from .filters import UserFilter
from .forms import CustomerForm


@staff_member_required
@permission_required('userprofile.view_user')
def customer_list(request):
    customers = (
        User.objects
        .prefetch_related('orders', 'addresses')
        .select_related('default_billing_address', 'default_shipping_address')
        .order_by('email'))
    customer_filter = UserFilter(request.GET, queryset=customers)
    customers = get_paginator_items(
        customer_filter.qs, settings.DASHBOARD_PAGINATE_BY,
        request.GET.get('page'))
    ctx = {
        'customers': customers, 'filter_set': customer_filter,
        'is_empty': not customer_filter.queryset.exists()}
    return TemplateResponse(request, 'dashboard/customer/list.html', ctx)


@staff_member_required
@permission_required('userprofile.view_user')
def customer_details(request, pk):
    queryset = User.objects.prefetch_related(
        'orders', 'addresses').select_related(
        'default_billing_address', 'default_shipping_address')
    customer = get_object_or_404(queryset, pk=pk)
    customer_orders = customer.orders.all()
    ctx = {'customer': customer, 'customer_orders': customer_orders}
    return TemplateResponse(request, 'dashboard/customer/detail.html', ctx)


@staff_member_required
@permission_required('userprofile.edit_user')
def customer_edit(request, pk=None):
    if pk:
        customer = get_object_or_404(User, pk=pk)
    else:
        customer = User()
    form = CustomerForm(request.POST or None, instance=customer)
    if form.is_valid():
        form.save()
        msg = pgettext_lazy(
            'Dashboard message', 'Updated customer') \
            if pk else pgettext_lazy(
            'Dashboard message', 'Added customer')
        if not pk:
            send_set_password_email(customer)
        messages.success(request, msg)
        return redirect('dashboard:customer-details', pk=customer.pk)
    ctx = {'form': form, 'customer': customer}
    return TemplateResponse(request, 'dashboard/customer/form.html', ctx)


@staff_member_required
@permission_required('userprofile.edit_staff')
@permission_required('userprofile.edit_user')
def customer_promote_to_staff(request, pk):
    customer = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        customer.is_staff = True
        customer.save()
        msg = pgettext_lazy(
            'Dashboard message',
            'Customer %s promoted to staff member') % customer
        messages.success(request, msg)
        return redirect('dashboard:customer-details', pk=customer.pk)
    return TemplateResponse(
        request, 'dashboard/customer/modal/confirm_promote.html',
        {'customer': customer})
