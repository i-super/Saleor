import pytest

from saleor.product.models import (
    AttributeChoiceValueTranslation, CategoryTranslation,
    CollectionTranslation, ProductAttributeTranslation, ProductTranslation,
    ProductVariantTranslation)


@pytest.fixture
def product_translation_pl(product):
    return ProductTranslation.objects.create(
        language_code='pl', product=product, name='Polish name',
        description="Polish description")


@pytest.fixture
def attribute_choice_translation_fr(translated_product_attribute):
    value = translated_product_attribute.product_attribute.values.first()
    return AttributeChoiceValueTranslation.objects.create(
        language_code='fr', attribute_choice_value=value,
        name='French name')


def test_translation(product, settings, product_translation_fr):
    assert product.translated.name == 'Test product'
    assert not product.translated.description

    settings.LANGUAGE_CODE = 'fr'
    assert product.translated.name == 'French name'
    assert product.translated.description == 'French description'


def test_translation_str_returns_str_of_instance(
        product, product_translation_fr, settings):
    assert str(product.translated) == str(product)
    settings.LANGUAGE_CODE = 'fr'
    assert str(
        product.translated.translation) == str(product_translation_fr)


def test_wrapper_gets_proper_wrapper(
        product, product_translation_fr, settings, product_translation_pl):
    assert product.translated.translation is None

    settings.LANGUAGE_CODE = 'fr'
    assert product.translated.translation == product_translation_fr

    settings.LANGUAGE_CODE = 'pl'
    assert product.translated.translation == product_translation_pl


def test_getattr(
        product, settings, product_translation_fr, product_type):
    settings.LANGUAGE_CODE = 'fr'
    assert product.translated.product_type == product_type


def test_translation_not_override_id(
        settings, product, product_translation_fr):
    settings.LANGUAGE_CODE = 'fr'
    translated_product = product.translated
    assert translated_product.id == product.id
    assert not translated_product.id == product_translation_fr


def test_collection_translation(settings, collection):
    settings.LANGUAGE_CODE = 'fr'
    french_name = 'French name'
    CollectionTranslation.objects.create(
        language_code='fr', name=french_name, collection=collection)
    assert collection.translated.name == french_name


def test_category_translation(settings, default_category):
    settings.LANGUAGE_CODE = 'fr'
    french_name = 'French name'
    french_description = 'French description'
    CategoryTranslation.objects.create(
        language_code='fr', name=french_name, description=french_description,
        category=default_category)
    assert default_category.translated.name == french_name
    assert default_category.translated.description == french_description


def test_product_variant_translation(settings, variant):
    settings.LANGUAGE_CODE = 'fr'
    french_name = 'French name'
    ProductVariantTranslation.objects.create(
        language_code='fr', name=french_name, product_variant=variant)
    assert variant.translated.name == french_name


def test_product_attribute_translation(settings, color_attribute):
    ProductAttributeTranslation.objects.create(
        language_code='fr', product_attribute=color_attribute,
        name='French name')
    assert not color_attribute.translated.name == 'French name'
    settings.LANGUAGE_CODE = 'fr'
    assert color_attribute.translated.name == 'French name'


def test_attribute_choice_value_translation(
        settings, product, attribute_choice_translation_fr):
    attribute = product.product_type.product_attributes.first().values.first()
    assert not attribute.translated.name == 'French name'
    settings.LANGUAGE_CODE = 'fr'
    assert attribute.translated.name == 'French name'


def test_voucher_translation(settings, voucher, voucher_translation_fr):
    assert not voucher.translated.name == 'French name'
    settings.LANGUAGE_CODE = 'fr'
    assert voucher.translated.name == 'French name'
