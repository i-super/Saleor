import json
from io import BytesIO
from unittest.mock import MagicMock, Mock, patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import HiddenInput
from django.forms.models import model_to_dict
from django.urls import reverse
from PIL import Image

from saleor.dashboard.product import ProductBulkAction
from saleor.dashboard.product.forms import (
    ProductBulkUpdate, ProductForm, ProductTypeForm, ProductVariantForm)
from saleor.product.forms import VariantChoiceField
from saleor.product.models import (
    AttributeChoiceValue, Collection, Product, ProductAttribute, ProductImage,
    ProductType, ProductVariant)

HTTP_STATUS_OK = 200
HTTP_REDIRECTION = 302


def create_image():
    img_data = BytesIO()
    image = Image.new('RGB', size=(1, 1), color=(255, 0, 0, 0))
    image.save(img_data, format='JPEG')
    image_name = 'product2'
    image = SimpleUploadedFile(
        image_name + '.jpg', img_data.getvalue(), 'image/png')
    return image, image_name


def test_product_variant_form(product):
    variant = product.variants.first()
    variant.name = ''
    variant.save()
    example_size = 'Small Size'
    data = {'attribute-size': example_size, 'sku': '1111', 'quantity': 2}
    form = ProductVariantForm(data, instance=variant)
    assert form.is_valid()
    form.save()
    variant.refresh_from_db()
    assert variant.name == example_size


def test_valid_product_type_form(color_attribute, size_attribute):
    data = {
        'name': "Testing Type",
        'product_attributes': [color_attribute.pk],
        'variant_attributes': [size_attribute.pk],
        'has_variants': True}
    form = ProductTypeForm(data)
    assert form.is_valid()

    # Don't allow same attribute in both fields
    data['variant_attributes'] = [color_attribute.pk, size_attribute.pk]
    data['product_attributes'] = [size_attribute.pk]
    form = ProductTypeForm(data)
    assert not form.is_valid()


def test_product_type_form_missing_variant_attributes(
        color_attribute, size_attribute, product_type):
    product_type.has_variants = True
    product_type.save()
    data = {
        'name': "Testing Type",
        'product_attributes': [color_attribute.pk],
        'variant_attributes': [size_attribute.pk],
        'has_variants': False}
    form = ProductTypeForm(data, instance=product_type)
    assert not form.is_valid()


def test_variantless_product_type_form(color_attribute, size_attribute):
    data = {
        'name': "Testing Type",
        'product_attributes': [color_attribute.pk],
        'variant_attributes': [],
        'has_variants': False}
    form = ProductTypeForm(data)
    assert form.is_valid()

    # Don't allow variant attributes when no variants
    data = {
        'name': "Testing Type",
        'product_attributes': [color_attribute.pk],
        'variant_attributes': [size_attribute.pk],
        'has_variants': False}
    form = ProductTypeForm(data)
    assert not form.is_valid()


def test_edit_used_product_type(db, default_category):
    product_type = ProductType.objects.create(
        name='New class', has_variants=True)
    product = Product.objects.create(
        name='Test product', price=10, product_type=product_type,
        category=default_category)
    ProductVariant.objects.create(product=product, sku='1234')

    # When all products have only one variant you can change
    # has_variants to false
    assert product.variants.all().count() == 1
    data = {
        'name': product_type.name,
        'product_attributes': product_type.product_attributes.all(),
        'variant_attributes': product_type.variant_attributes.all(),
        'has_variants': False}
    form = ProductTypeForm(data, instance=product_type)
    assert form.is_valid()

    data = {
        'name': product_type.name,
        'product_attributes': product_type.product_attributes.all(),
        'variant_attributes': product_type.variant_attributes.all(),
        'has_variants': True}
    form = ProductTypeForm(data, instance=product_type)
    assert form.is_valid()

    # Test has_variants validator which prevents turning off when product
    # has multiple variants
    ProductVariant.objects.create(product=product, sku='12345')
    assert product.variants.all().count() == 2
    data = {
        'name': product_type.name,
        'product_attributes': product_type.product_attributes.all(),
        'variant_attributes': product_type.variant_attributes.all(),
        'has_variants': False}
    form = ProductTypeForm(data, instance=product_type)
    assert not form.is_valid()
    assert 'has_variants' in form.errors.keys()


def test_change_attributes_in_product_form(db, product, color_attribute):
    product_type = product.product_type
    text_attribute = ProductAttribute.objects.create(
        slug='author', name='Author')
    product_type.product_attributes.add(text_attribute)
    color_value = color_attribute.values.first()
    new_author = 'Main Tester'
    data = {
        'name': product.name,
        'price': product.price.amount,
        'category': product.category.pk,
        'description': 'description',
        'attribute-author': new_author,
        'attribute-color': color_value.pk}
    form = ProductForm(data, instance=product)
    assert form.is_valid()
    product = form.save()
    assert product.attributes[str(color_attribute.pk)] == str(color_value.pk)

    # Check that new attribute was created for author
    author_value = AttributeChoiceValue.objects.get(name=new_author)
    assert product.attributes[str(text_attribute.pk)] == str(author_value.pk)


def test_attribute_list(db, product, color_attribute, admin_client):
    assert len(ProductAttribute.objects.all()) == 2
    response = admin_client.get(reverse('dashboard:product-attributes'))
    assert response.status_code == 200


def test_attribute_details(color_attribute, admin_client):
    url = reverse(
        'dashboard:product-attribute-details',
        kwargs={'pk': color_attribute.pk})
    response = admin_client.get(url)
    assert response.status_code == 200


def test_attribute_add(color_attribute, admin_client):
    assert len(ProductAttribute.objects.all()) == 1
    url = reverse('dashboard:product-attribute-add')
    data = {'name': 'test', 'slug': 'test'}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert len(ProductAttribute.objects.all()) == 2


def test_attribute_add_not_valid(color_attribute, admin_client):
    assert len(ProductAttribute.objects.all()) == 1
    url = reverse('dashboard:product-attribute-add')
    data = {}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert len(ProductAttribute.objects.all()) == 1


def test_attribute_edit(color_attribute, admin_client):
    assert len(ProductAttribute.objects.all()) == 1
    url = reverse(
        'dashboard:product-attribute-update',
        kwargs={'pk': color_attribute.pk})
    data = {'name': 'new_name', 'slug': 'new_slug'}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert len(ProductAttribute.objects.all()) == 1
    color_attribute.refresh_from_db()
    assert color_attribute.name == 'new_name'
    assert color_attribute.slug == 'new_slug'


def test_attribute_delete(color_attribute, admin_client):
    assert len(ProductAttribute.objects.all()) == 1
    url = reverse(
        'dashboard:product-attribute-delete',
        kwargs={'pk': color_attribute.pk})
    response = admin_client.post(url, follow=True)
    assert response.status_code == 200
    assert len(ProductAttribute.objects.all()) == 0


def test_attribute_choice_value_add(color_attribute, admin_client):
    values = AttributeChoiceValue.objects.filter(attribute=color_attribute.pk)
    assert len(values) == 2
    url = reverse(
        'dashboard:product-attribute-value-add',
        kwargs={'attribute_pk': color_attribute.pk})
    data = {'name': 'Pink', 'color': '#FFF', 'attribute': color_attribute.pk}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    values = AttributeChoiceValue.objects.filter(attribute=color_attribute.pk)
    assert len(values) == 3


def test_attribute_choice_value_add_not_valid(color_attribute, admin_client):
    values = AttributeChoiceValue.objects.filter(attribute=color_attribute.pk)
    assert len(values) == 2
    url = reverse(
        'dashboard:product-attribute-value-add',
        kwargs={'attribute_pk': color_attribute.pk})
    data = {}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    values = AttributeChoiceValue.objects.filter(attribute=color_attribute.pk)
    assert len(values) == 2


def test_attribute_choice_value_edit(color_attribute, admin_client):
    values = AttributeChoiceValue.objects.filter(attribute=color_attribute.pk)
    assert len(values) == 2
    url = reverse(
        'dashboard:product-attribute-value-update',
        kwargs={'attribute_pk': color_attribute.pk, 'value_pk': values[0].pk})
    data = {'name': 'Pink', 'color': '#FFF', 'attribute': color_attribute.pk}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    values = AttributeChoiceValue.objects.filter(
        attribute=color_attribute.pk, name='Pink')
    assert len(values) == 1
    assert values[0].name == 'Pink'


def test_attribute_choice_value_delete(color_attribute, admin_client):
    values = AttributeChoiceValue.objects.filter(attribute=color_attribute.pk)
    assert len(values) == 2
    deleted_value = values[0]
    url = reverse(
        'dashboard:product-attribute-value-delete',
        kwargs={
            'attribute_pk': color_attribute.pk, 'value_pk': deleted_value.pk})
    response = admin_client.post(url, follow=True)
    assert response.status_code == 200
    values = AttributeChoiceValue.objects.filter(attribute=color_attribute.pk)
    assert len(values) == 1
    assert deleted_value not in values


def test_get_formfield_name_with_unicode_characters(db):
    text_attribute = ProductAttribute.objects.create(
        slug='ąęαβδηθλμπ', name='ąęαβδηθλμπ')
    assert text_attribute.get_formfield_name() == 'attribute-ąęαβδηθλμπ'


def test_view_product_toggle_publish(db, admin_client, product):
    url = reverse('dashboard:product-publish', kwargs={'pk': product.pk})
    response = admin_client.post(url)
    assert response.status_code == HTTP_STATUS_OK
    data = {'success': True, 'is_published': False}
    assert json.loads(response.content.decode('utf8')) == data
    admin_client.post(url)
    product.refresh_from_db()
    assert product.is_published


def test_view_product_not_deleted_before_confirmation(
        db, admin_client, product):
    url = reverse('dashboard:product-delete', kwargs={'pk': product.pk})
    response = admin_client.get(url)
    assert response.status_code == HTTP_STATUS_OK
    product.refresh_from_db()


def test_view_product_delete(db, admin_client, product):
    url = reverse('dashboard:product-delete', kwargs={'pk': product.pk})
    response = admin_client.post(url)
    assert response.status_code == HTTP_REDIRECTION
    assert not Product.objects.filter(pk=product.pk)


def test_view_product_type_not_deleted_before_confirmation(
        admin_client, product):
    product_type = product.product_type
    url = reverse(
        'dashboard:product-type-delete', kwargs={'pk': product_type.pk})
    response = admin_client.get(url)
    assert response.status_code == HTTP_STATUS_OK
    assert ProductType.objects.filter(pk=product_type.pk)


def test_view_product_type_delete(db, admin_client, product):
    product_type = product.product_type
    url = reverse(
        'dashboard:product-type-delete', kwargs={'pk': product_type.pk})
    response = admin_client.post(url)
    assert response.status_code == HTTP_REDIRECTION
    assert not ProductType.objects.filter(pk=product_type.pk)


def test_view_product_variant_not_deleted_before_confirmation(
        admin_client, product):
    product_variant_pk = product.variants.first().pk
    url = reverse(
        'dashboard:variant-delete',
        kwargs={
            'product_pk': product.pk,
            'variant_pk': product_variant_pk})
    response = admin_client.get(url)
    assert response.status_code == HTTP_STATUS_OK
    assert ProductVariant.objects.filter(pk=product_variant_pk)


def test_view_product_variant_delete(admin_client, product):
    product_variant_pk = product.variants.first().pk
    url = reverse(
        'dashboard:variant-delete',
        kwargs={
            'product_pk': product.pk,
            'variant_pk': product_variant_pk})
    response = admin_client.post(url)
    assert response.status_code == HTTP_REDIRECTION
    assert not ProductVariant.objects.filter(pk=product_variant_pk)


def test_view_attribute_not_deleted_before_confirmation(
        admin_client, color_attribute):
    url = reverse(
        'dashboard:product-attribute-delete',
        kwargs={'pk': color_attribute.pk})
    response = admin_client.get(url)
    assert response.status_code == HTTP_STATUS_OK
    assert ProductAttribute.objects.filter(pk=color_attribute.pk)


def test_view_attribute_delete(admin_client, color_attribute):
    url = reverse(
        'dashboard:product-attribute-delete',
        kwargs={'pk': color_attribute.pk})
    response = admin_client.post(url)
    assert response.status_code == HTTP_REDIRECTION
    assert not ProductAttribute.objects.filter(pk=color_attribute.pk)


def test_view_product_image_not_deleted_before_confirmation(
        admin_client, product_with_image):
    product_image = product_with_image.images.all()[0]
    url = reverse(
        'dashboard:product-image-delete',
        kwargs={
            'img_pk': product_image.pk,
            'product_pk': product_with_image.pk})
    response = admin_client.get(url)
    assert response.status_code == HTTP_STATUS_OK
    assert ProductImage.objects.filter(pk=product_image.pk).count()


def test_view_product_image_delete(admin_client, product_with_image):
    product_image = product_with_image.images.all()[0]
    url = reverse(
        'dashboard:product-image-delete',
        kwargs={
            'img_pk': product_image.pk,
            'product_pk': product_with_image.pk})
    response = admin_client.post(url)
    assert response.status_code == HTTP_REDIRECTION
    assert not ProductImage.objects.filter(pk=product_image.pk)


def test_view_reorder_product_images(admin_client, product_with_images):
    order_before = [img.pk for img in product_with_images.images.all()]
    ordered_images = list(reversed(order_before))
    url = reverse(
        'dashboard:product-images-reorder',
        kwargs={'product_pk': product_with_images.pk})
    data = {'ordered_images': ordered_images}
    response = admin_client.post(
        url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    order_after = [img.pk for img in product_with_images.images.all()]
    assert response.status_code == 200
    assert order_after == ordered_images


def test_view_invalid_reorder_product_images(
        admin_client, product_with_images):
    order_before = [img.pk for img in product_with_images.images.all()]
    ordered_images = list(reversed(order_before)).append(3)
    url = reverse(
        'dashboard:product-images-reorder',
        kwargs={'product_pk': product_with_images.pk})
    data = {'ordered_images': ordered_images}
    response = admin_client.post(
        url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    assert response.status_code == 400
    resp_decoded = json.loads(response.content.decode('utf-8'))
    assert 'error' in resp_decoded
    assert 'ordered_images' in resp_decoded['error']


@patch('saleor.dashboard.product.forms.create_product_thumbnails.delay')
def test_view_product_image_add(
        mock_create_thumbnails, admin_client, product_with_image):
    assert len(ProductImage.objects.all()) == 1
    assert len(product_with_image.images.all()) == 1
    url = reverse(
        'dashboard:product-image-add',
        kwargs={'product_pk': product_with_image.pk})
    response = admin_client.get(url)
    assert response.status_code == 200
    image, image_name = create_image()
    data = {'image_0': image, 'alt': ['description']}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert len(ProductImage.objects.all()) == 2
    product_with_image.refresh_from_db()
    images = product_with_image.images.all()
    assert len(images) == 2
    assert image_name in images[1].image.name
    assert images[1].alt == 'description'
    mock_create_thumbnails.assert_called_once_with(images[1].pk)


@patch('saleor.dashboard.product.forms.create_product_thumbnails.delay')
def test_view_product_image_edit_same_image_add_description(
        mock_create_thumbnails, admin_client, product_with_image):
    assert len(product_with_image.images.all()) == 1
    product_image = product_with_image.images.all()[0]
    url = reverse(
        'dashboard:product-image-update',
        kwargs={
            'img_pk': product_image.pk,
            'product_pk': product_with_image.pk})
    response = admin_client.get(url)
    assert response.status_code == 200
    data = {'image_1': ['0.49x0.59'], 'alt': ['description']}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert len(product_with_image.images.all()) == 1
    product_image.refresh_from_db()
    assert product_image.alt == 'description'
    mock_create_thumbnails.assert_called_once_with(product_image.pk)


@patch('saleor.dashboard.product.forms.create_product_thumbnails.delay')
def test_view_product_image_edit_new_image(
        mock_create_thumbnails, admin_client, product_with_image):
    assert len(product_with_image.images.all()) == 1
    product_image = product_with_image.images.all()[0]
    url = reverse(
        'dashboard:product-image-update',
        kwargs={
            'img_pk': product_image.pk,
            'product_pk': product_with_image.pk})
    response = admin_client.get(url)
    assert response.status_code == 200
    image, image_name = create_image()
    data = {'image_0': image, 'alt': ['description']}
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert len(product_with_image.images.all()) == 1
    product_image.refresh_from_db()
    assert image_name in product_image.image.name
    assert product_image.alt == 'description'
    mock_create_thumbnails.assert_called_once_with(product_image.pk)


def perform_bulk_action(product_list, action):
    """Perform given bulk action on given product list."""
    data = {'action': action, 'products': [p.pk for p in product_list]}
    form = ProductBulkUpdate(data)
    assert form.is_valid()
    form.save()


def test_product_bulk_update_form_can_publish_products(product_list):
    perform_bulk_action(product_list, ProductBulkAction.PUBLISH)
    for p in product_list:
        p.refresh_from_db()
        assert p.is_published


def test_product_bulk_update_form_can_unpublish_products(product_list):
    perform_bulk_action(product_list, ProductBulkAction.UNPUBLISH)
    for p in product_list:
        p.refresh_from_db()
        assert not p.is_published


def test_product_list_filters(admin_client, product_list):
    data = {'price_1': [''], 'price_0': [''], 'is_featured': [''],
            'name': ['Test'], 'sort_by': [''], 'is_published': ['']}
    url = reverse('dashboard:product-list')
    response = admin_client.get(url, data)
    assert response.status_code == 200
    assert list(response.context['filter_set'].qs) == product_list


def test_product_list_filters_sort_by(admin_client, product_list):
    data = {'price_1': [''], 'price_0': [''], 'is_featured': [''],
            'name': ['Test'], 'sort_by': ['name'], 'is_published': ['']}
    url = reverse('dashboard:product-list')
    response = admin_client.get(url, data)
    assert response.status_code == 200
    assert list(response.context['filter_set'].qs) == product_list

    data = {'price_1': [''], 'price_0': [''], 'is_featured': [''],
            'name': ['Test'], 'sort_by': ['-name'], 'is_published': ['']}
    url = reverse('dashboard:product-list')
    response = admin_client.get(url, data)
    assert response.status_code == 200
    assert list(response.context['filter_set'].qs) == product_list[::-1]


def test_product_list_filters_is_published(
        admin_client, product_list, default_category):
    data = {'price_1': [''], 'price_0': [''], 'is_featured': [''],
            'name': ['Test'], 'sort_by': ['name'],
            'category': default_category.pk, 'is_published': ['1']}
    url = reverse('dashboard:product-list')
    response = admin_client.get(url, data)
    assert response.status_code == 200
    result = list(response.context['filter_set'].qs)
    assert result == [product_list[0], product_list[2]]


def test_product_list_filters_no_results(admin_client, product_list):
    data = {'price_1': [''], 'price_0': [''], 'is_featured': [''],
            'name': ['BADTest'], 'sort_by': [''],
            'is_published': ['']}
    url = reverse('dashboard:product-list')
    response = admin_client.get(url, data)
    assert response.status_code == 200
    assert list(response.context['filter_set'].qs) == []


def test_product_list_pagination(admin_client, product_list):
    settings.DASHBOARD_PAGINATE_BY = 1
    data = {'page': '1'}
    url = reverse('dashboard:product-list')
    response = admin_client.get(url, data)
    assert response.status_code == 200
    assert not response.context['filter_set'].is_bound_unsorted

    data = {'page': '2'}
    url = reverse('dashboard:product-list')
    response = admin_client.get(url, data)
    assert response.status_code == 200
    assert not response.context['filter_set'].is_bound_unsorted


def test_product_list_pagination_with_filters(admin_client, product_list):
    settings.DASHBOARD_PAGINATE_BY = 1
    data = {'page': '1', 'price_1': [''], 'price_0': [''], 'is_featured': [''],
            'name': ['Test'], 'sort_by': ['name'], 'is_published': ['']}
    url = reverse('dashboard:product-list')
    response = admin_client.get(url, data)
    assert response.status_code == 200
    assert list(response.context['products'])[0] == product_list[0]

    data = {'page': '2', 'price_1': [''], 'price_0': [''], 'is_featured': [''],
            'name': ['Test'], 'sort_by': ['name'], 'is_published': ['']}
    url = reverse('dashboard:product-list')
    response = admin_client.get(url, data)
    assert response.status_code == 200
    assert list(response.context['products'])[0] == product_list[1]


def test_product_select_types(admin_client, product_type):
    url = reverse('dashboard:product-add-select-type')
    response = admin_client.get(url)
    assert response.status_code == HTTP_STATUS_OK

    data = {'product_type': product_type.pk}
    response = admin_client.post(url, data)
    assert response.get('location') == reverse(
        'dashboard:product-add', kwargs={'type_pk': product_type.pk})
    assert response.status_code == HTTP_REDIRECTION


def test_product_select_types_by_ajax(admin_client, product_type):
    url = reverse('dashboard:product-add-select-type')
    data = {'product_type': product_type.pk}

    response = admin_client.post(
        url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    resp_decoded = json.loads(response.content.decode('utf-8'))
    assert response.status_code == 200
    assert resp_decoded.get('redirectUrl') == reverse(
        'dashboard:product-add', kwargs={'type_pk': product_type.pk})


def test_hide_field_in_variant_choice_field_form():
    form = VariantChoiceField(Mock)
    variants, cart = MagicMock(), MagicMock()
    variants.count.return_value = 1
    variants.all()[0].pk = 'test'
    form.update_field_data(variants, discounts=None, taxes=None)
    assert isinstance(form.widget, HiddenInput)
    assert form.widget.attrs.get('value') == 'test'


def test_assign_collection_to_product(product):
    collection = Collection.objects.create(name='test_collections')
    data = {
        'name': product.name,
        'price': product.price.amount,
        'category': product.category.pk,
        'description': 'description',
        'collections': [collection.pk]}
    form = ProductForm(data, instance=product)
    assert form.is_valid()
    form.save()
    assert product.collections.first().name == 'test_collections'
    assert collection.products.first().name == product.name


def test_sanitize_product_description(product_type, default_category):
    product = Product.objects.create(
        name='Test Product', price=10, description='', pk=10,
        product_type=product_type, category=default_category)
    data = model_to_dict(product)
    data['description'] = (
        '<b>bold</b><p><i>italic</i></p><h2>Header</h2><h3>subheader</h3>'
        '<blockquote>quote</blockquote>'
        '<p><a href="www.mirumee.com">link</a></p>'
        '<p>an <script>evil()</script>example</p>')
    data['price'] = 20
    form = ProductForm(data, instance=product)
    assert form.is_valid()
    form.save()
    assert product.description == (
        '<b>bold</b><p><i>italic</i></p><h2>Header</h2><h3>subheader</h3>'
        '<blockquote>quote</blockquote>'
        '<p><a href="www.mirumee.com">link</a></p>'
        '<p>an &lt;script&gt;evil()&lt;/script&gt;example</p>')

    assert product.seo_description == (
        'bolditalicHeadersubheaderquotelinkan evil()example')


def test_set_product_seo_description(unavailable_product):
    seo_description = (
        'This is a dummy product. '
        'HTML <b>shouldn\'t be removed</b> since it\'s a simple text field.')
    data = model_to_dict(unavailable_product)
    data['price'] = 20
    data['description'] = 'a description'
    data['seo_description'] = seo_description

    form = ProductForm(data, instance=unavailable_product)

    assert form.is_valid()
    form.save()
    assert unavailable_product.seo_description == seo_description


def test_set_product_description_too_long_for_seo(unavailable_product):
    description = (
        'Saying it fourth made saw light bring beginning kind over herb '
        'won\'t creepeth multiply dry rule divided fish herb cattle greater '
        'fly divided midst, gathering can\'t moveth seed greater subdue. '
        'Lesser meat living fowl called. Dry don\'t wherein. Doesn\'t above '
        'form sixth. Image moving earth without forth light whales. Seas '
        'were first form fruit that form they\'re, shall air. And. Good of'
        'signs darkness be place. Was. Is form it. Whose. Herb signs stars '
        'fill own fruit wherein. '
        'Don\'t set man face living fifth Thing the whales were. '
        'You fish kind. '
        'Them, his under wherein place first you night gathering.')

    data = model_to_dict(unavailable_product)
    data['price'] = 20
    data['description'] = description

    form = ProductForm(data, instance=unavailable_product)

    assert form.is_valid()
    form.save()

    assert len(unavailable_product.seo_description) <= 300
    assert unavailable_product.seo_description == (
        'Saying it fourth made saw light bring beginning kind over herb '
        'won\'t creepeth multiply dry rule divided fish herb cattle greater '
        'fly divided midst, gathering can\'t moveth seed greater subdue. '
        'Lesser meat living fowl called. Dry don\'t wherein. Doesn\'t above '
        'form sixth. Image moving earth without f...'
    )
