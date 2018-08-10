import graphene
from django.contrib.auth import get_user_model, models as auth_models
from graphene import relay

from ...account import models
from ..core.types.common import CountableDjangoObjectType, PermissionDisplay
from ..utils import format_permissions_for_display


class AddressInput(graphene.InputObjectType):
    first_name = graphene.String(description='Given name.')
    last_name = graphene.String(description='Family name.')
    company_name = graphene.String(description='Company or organization.')
    street_address_1 = graphene.String(description='Address.')
    street_address_2 = graphene.String(description='Address.')
    city = graphene.String(description='City.')
    city_area = graphene.String(description='District.')
    postal_code = graphene.String(description='Postal code.')
    country = graphene.String(description='Country.')
    country_area = graphene.String(description='State or province.')
    phone = graphene.String(description='Phone number.')


class Address(CountableDjangoObjectType):
    class Meta:
        exclude_fields = ['user_set', 'user_addresses']
        description = 'Represents user address data.'
        interfaces = [relay.Node]
        model = models.Address


class User(CountableDjangoObjectType):
    permissions = graphene.List(PermissionDisplay)

    class Meta:
        exclude_fields = [
            'date_joined', 'password', 'is_superuser', 'ordernote_set',
            'orderhistoryentry_set', 'last_login']
        description = 'Represents user data.'
        interfaces = [relay.Node]
        model = get_user_model()
        filter_fields = ['is_staff']

    def resolve_permissions(self, info, **kwargs):
        if self.is_superuser:
            permissions = auth_models.Permission.objects.all()
        else:
            permissions = (
                self.user_permissions.all() |
                auth_models.Permission.objects.filter(group__user=self))
        permissions = permissions.select_related('content_type')
        return format_permissions_for_display(permissions)
