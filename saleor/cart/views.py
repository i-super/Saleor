from __future__ import unicode_literals

from django.contrib import messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import ugettext as _
from satchless.item import Partitioner

from .forms import ReplaceCartLineFormSet
from . import Cart


def index(request):
    cart = Cart.from_data(request.cart)
    cart_partitioner = Partitioner(cart)

    formset = ReplaceCartLineFormSet(request.POST or None,
                                     cart=cart)
    if formset.is_valid():
        msg = _('Successfully updated product quantities.')
        messages.success(request, msg)
        formset.save()
        request.cart = formset.get_cart().as_data()
        return redirect('cart:index')
    return TemplateResponse(
        request, 'cart/index.html', {
            'cart': cart_partitioner,
            'formset': formset})
