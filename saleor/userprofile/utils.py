from .models import Address, User


def store_user_address(user, address, billing=False, shipping=False):
    data = Address.objects.as_data(address)
    entry = user.addresses.get_or_create(**data)[0]
    changed = False
    if billing and not user.default_billing_address_id:
        user.default_billing_address = entry
        changed = True
    if shipping and not user.default_shipping_address_id:
        user.default_shipping_address = entry
        changed = True
    if changed:
        user.save()
    return entry

def get_customers(request):
    return User.objects.filter(is_staff=False, is_superuser=False)
