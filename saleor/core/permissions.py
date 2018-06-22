from django.contrib.auth.models import Permission

MODELS_PERMISSIONS = [
    'menu.view_menu',
    'menu.edit_menu',
    'order.view_order',
    'order.edit_order',
    'page.view_page',
    'page.edit_page',
    'product.view_category',
    'product.edit_category',
    'product.view_product',
    'product.edit_product',
    'product.view_properties',
    'product.edit_properties',
    'sale.view_sale',
    'sale.edit_sale',
    'shipping.view_shipping',
    'shipping.edit_shipping',
    'site.edit_settings',
    'site.view_settings',
    'user.view_user',
    'user.edit_user',
    'user.view_group',
    'user.edit_group',
    'user.view_staff',
    'user.edit_staff',
    'user.impersonate_user',
    'voucher.view_voucher',
    'voucher.edit_voucher',
]


def get_permissions():
    codenames = [permission.split('.')[1] for permission in MODELS_PERMISSIONS]
    return Permission.objects.filter(codename__in=codenames).prefetch_related(
        'content_type').order_by('codename')
