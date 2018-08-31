import graphene
from django.conf import settings
from django_countries import countries
from graphql_jwt.decorators import permission_required
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE

from ...core.permissions import get_permissions
from ...site import models as site_models
from ..core.types.common import (
    CountryDisplay, LanguageDisplay, PermissionDisplay, WeightUnitsEnum)
from ..menu.types import Menu
from ..product.types import Collection
from ..utils import format_permissions_for_display


class AuthorizationKey(graphene.ObjectType):
    name = graphene.String(description='Name of the key.', required=True)
    key = graphene.String(description='Value of the key.', required=True)


class Domain(graphene.ObjectType):
    host = graphene.String(
        description='The host name of the domain.', required=True)
    ssl_enabled = graphene.Boolean(
        description='Inform if SSL is enabled.', required=True)
    url = graphene.String(
        description='Shop\'s absolute URL.', required=True)

    class Meta:
        description = 'Represents shop\'s domain.'


class Navigation(graphene.ObjectType):
    main = graphene.Field(Menu, description='Main navigation bar.')
    secondary = graphene.Field(Menu, description='Secondary navigation bar.')

    class Meta:
        description = 'Represents shop\'s navigation menus.'


class Shop(graphene.ObjectType):
    authorization_keys = graphene.List(
        AuthorizationKey, description='List of configured authorization keys.',
        required=True)
    countries = graphene.List(
        CountryDisplay, description='List of countries available in the shop.',
        required=True)
    currencies = graphene.List(
        graphene.String, description='List of available currencies.',
        required=True)
    default_currency = graphene.String(
        description='Default shop\'s currency.', required=True)
    description = graphene.String(description='Shop\'s description.')
    domain = graphene.Field(
        Domain, required=True, description='Shop\'s domain data.')
    homepage_collection = graphene.Field(
        Collection, description='Collection displayed on homepage')
    languages = graphene.List(
        LanguageDisplay,
        description='List of the shops\'s supported languages.', required=True)
    name = graphene.String(description='Shop\'s name.', required=True)
    navigation = graphene.Field(
        Navigation, description='Shop\'s navigation.')
    permissions = graphene.List(
        PermissionDisplay, description='List of available permissions.',
        required=True)
    phone_prefixes = graphene.List(
        graphene.String, description='List of possible phone prefixes.',
        required=True)
    header_text = graphene.String(description='Header text')
    include_taxes_in_prices = graphene.Boolean(
        description='Include taxes in prices')
    display_gross_prices = graphene.Boolean(
        description='Display prices with tax in store')
    track_inventory_by_default = graphene.Boolean(
        description='Enable inventory tracking')
    default_weight_unit = WeightUnitsEnum(description='Default weight unit')

    class Meta:
        description = '''
        Represents a shop resource containing general shop\'s data
        and configuration.'''

    @permission_required('site.manage_settings')
    def resolve_authorization_keys(self, info):
        return site_models.AuthorizationKey.objects.all()

    def resolve_countries(self, info):
        return [
            CountryDisplay(code=country[0], country=country[1])
            for country in countries]

    def resolve_currencies(self, info):
        return settings.AVAILABLE_CURRENCIES

    def resolve_domain(self, info):
        site = info.context.site
        return Domain(
            host=site.domain,
            ssl_enabled=settings.ENABLE_SSL,
            url=info.context.build_absolute_uri('/'))

    def resolve_default_currency(self, info):
        return settings.DEFAULT_CURRENCY

    def resolve_description(self, info):
        return info.context.site.settings.description

    def resolve_homepage_collection(self, info):
        return info.context.site.settings.homepage_collection

    def resolve_languages(self, info):
        return [
            LanguageDisplay(code=language[0], language=language[1])
            for language in settings.LANGUAGES]

    def resolve_name(self, info):
        return info.context.site.name

    def resolve_navigation(self, info):
        site_settings = info.context.site.settings
        return Navigation(
            main=site_settings.top_menu, secondary=site_settings.bottom_menu)

    @permission_required('site.manage_settings')
    def resolve_permissions(self, info):
        permissions = get_permissions()
        return format_permissions_for_display(permissions)

    def resolve_phone_prefixes(self, info):
        return list(COUNTRY_CODE_TO_REGION_CODE.keys())

    def resolve_header_text(self, info):
        return info.context.site.settings.header_text

    def resolve_include_taxes_in_prices(self, info):
        return info.context.site.settings.include_taxes_in_prices

    def resolve_display_gross_prices(self, info):
        return info.context.site.settings.display_gross_prices

    def resolve_track_inventory_by_default(self, info):
        return info.context.site.settings.track_inventory_by_default

    def resolve_default_weight_unit(self, info):
        return info.context.site.settings.default_weight_unit
