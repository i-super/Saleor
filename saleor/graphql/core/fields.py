import graphene
from django_prices.models import MoneyField, TaxedMoneyField
from graphene_django.converter import convert_django_field

from .types.money import Money, TaxedMoney


@convert_django_field.register(TaxedMoneyField)
def convert_field_taxed_money(field, registry=None):
    return graphene.Field(TaxedMoney)


@convert_django_field.register(MoneyField)
def convert_field_money(field, registry=None):
    return graphene.Field(Money)
