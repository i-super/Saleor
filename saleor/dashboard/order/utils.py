from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import get_template

from ...order.models import DeliveryGroup, Order

INVOICE_TEMPLATE = 'dashboard/order/pdf/invoice.html'
PACKING_SLIP_TEMPLATE = 'dashboard/order/pdf/packing_slip.html'


def get_statics_absolute_url(request):
    site = get_current_site(request)
    absolute_url = '%(protocol)s://%(domain)s%(static_url)s' % {
        'protocol': 'https' if request.is_secure() else 'http',
        'domain': site.domain,
        'static_url': settings.STATIC_URL,
    }
    return absolute_url


def _create_pdf(rendered_template, absolute_url):
    from weasyprint import HTML
    pdf_file = (HTML(string=rendered_template, base_url=absolute_url)
                .write_pdf())
    return pdf_file


def create_invoice_pdf(order_pk, absolute_url):
    order = (Order.objects.prefetch_related(
        'user', 'shipping_address', 'billing_address', 'voucher',
        'groups').get(pk=order_pk))
    shipping_methods = [
        {'name': d.shipping_method_name,
         'price': d.shipping_price} for d in order.groups.all()]
    ctx = {'order': order, 'shipping_methods': shipping_methods}
    rendered_template = get_template(INVOICE_TEMPLATE).render(ctx)
    pdf_file = _create_pdf(rendered_template, absolute_url)
    return pdf_file, order


def create_packing_slip_pdf(group_pk, absolute_url):
    group = (DeliveryGroup.objects.prefetch_related(
        'lines', 'order', 'order__user', 'order__shipping_address',
        'order__billing_address').get(pk=group_pk))
    ctx = {'group': group}
    rendered_template = get_template(PACKING_SLIP_TEMPLATE).render(ctx)
    pdf_file = _create_pdf(rendered_template, absolute_url)
    return pdf_file, group
