import json
from unittest.mock import patch

import graphene
import pytest
from django.forms.models import model_to_dict
from django.shortcuts import reverse
from django.utils.text import slugify
from prices import Money

from saleor.graphql.core.mutations import (
    ModelFormMutation, ModelFormUpdateMutation)
from saleor.page.models import Page
from saleor.product.models import (
    Category, Product, ProductAttribute, ProductType)

from .utils import get_graphql_content


def test_create_token_mutation(admin_client, staff_user):
    query = '''
    mutation {
        tokenCreate(email: "%(email)s", password: "%(password)s") {
            token
            errors {
                field
                message
            }
        }
    }
    '''
    success_query = query % {'email': staff_user.email, 'password': 'password'}
    response = admin_client.post(reverse('api'), {'query': success_query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    token_data = content['data']['tokenCreate']
    assert token_data['token']
    assert not token_data['errors']

    error_query = query % {'email': staff_user.email, 'password': 'wat'}
    response = admin_client.post(reverse('api'), {'query': error_query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    token_data = content['data']['tokenCreate']
    assert not token_data['token']
    errors = token_data['errors']
    assert errors
    assert not errors[0]['field']


def test_category_query(client, product):
    category = Category.objects.first()
    query = '''
    query {
        category(id: "%(category_pk)s") {
            id
            name
            ancestors {
                edges {
                    node {
                        name
                    }
                }
            }
            children {
                edges {
                    node {
                        name
                    }
                }
            }
        }
    }
    ''' % {'category_pk': graphene.Node.to_global_id('Category', category.pk)}
    response = client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    category_data = content['data']['category']
    assert category_data is not None
    assert category_data['name'] == category.name
    assert (
        len(category_data['ancestors']['edges']) ==
        category.get_ancestors().count())
    assert (
        len(category_data['children']['edges']) ==
        category.get_children().count())


def test_fetch_all_products(client, product):
    query = '''
    query {
        products {
            totalCount
            edges {
                node {
                    id
                }
            }
        }
    }
    '''
    response = client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    num_products = Product.objects.count()
    assert content['data']['products']['totalCount'] == num_products
    assert len(content['data']['products']['edges']) == num_products


@pytest.mark.djangodb
def test_fetch_unavailable_products(client, product):
    Product.objects.update(is_published=False)
    query = '''
    query {
        products {
            totalCount
            edges {
                node {
                    id
                }
            }
        }
    }
    '''
    response = client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    assert content['data']['products']['totalCount'] == 0
    assert not content['data']['products']['edges']


def test_product_query(admin_client, product):
    category = Category.objects.first()
    product = category.products.first()
    query = '''
    query {
        category(id: "%(category_id)s") {
            products {
                edges {
                    node {
                        id
                        name
                        url
                        thumbnailUrl
                        images {
                            edges {
                                node {
                                    url
                                }
                            }
                        }
                        variants {
                            edges {
                                node {
                                    name
                                    stockQuantity
                                    }
                                }
                        }
                        availability {
                            available,
                            priceRange {
                                start {
                                    gross {
                                        amount
                                        currency
                                        localized
                                    }
                                    net {
                                        amount
                                        currency
                                        localized
                                    }
                                    currency
                                }
                            }
                        }
                        purchaseCost{
                            start{
                                amount
                            }
                            stop{
                                amount
                            }
                        }
                        margin {
                            start
                            stop
                        }
                    }
                }
            }
        }
    }
    ''' % {'category_id': graphene.Node.to_global_id('Category', category.id)}
    response = admin_client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    assert content['data']['category'] is not None
    product_edges_data = content['data']['category']['products']['edges']
    assert len(product_edges_data) == category.products.count()
    product_data = product_edges_data[0]['node']
    assert product_data['name'] == product.name
    assert product_data['url'] == product.get_absolute_url()
    gross = product_data['availability']['priceRange']['start']['gross']
    assert float(gross['amount']) == float(product.price.amount)
    from saleor.product.utils.costs import get_product_costs_data
    purchase_cost, margin = get_product_costs_data(product)
    assert purchase_cost.start.amount == product_data[
        'purchaseCost']['start']['amount']
    assert purchase_cost.stop.amount == product_data[
        'purchaseCost']['stop']['amount']
    assert margin[0] == product_data['margin'][0]['start']
    assert margin[1] == product_data['margin'][0]['stop']


def test_product_with_collections(admin_client, product, collection):
    query = '''
        query getProduct($productID: ID!) {
            product(id: $productID) {
                collections(first: 1) {
                    edges {
                        node {
                            name
                        }
                    }
                }
            }
        }
        '''
    product.collections.add(collection)
    product.save()
    product_id = graphene.Node.to_global_id('Product', product.id)

    variables = json.dumps({'productID': product_id})
    response = admin_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['product']
    assert data['collections']['edges'][0]['node']['name'] == collection.name
    assert len(data['collections']['edges']) == 1


def test_filter_product_by_category(client, product):
    category = product.category
    query = '''
    query getProducts($categoryId: ID) {
        products(category: $categoryId) {
            edges {
                node {
                    name
                }
            }
        }
    }
    '''
    response = client.post(
        reverse('api'),
        {
            'query': query,
            'variables': json.dumps(
                {
                    'categoryId': graphene.Node.to_global_id(
                        'Category', category.id)}),
            'operationName': 'getProducts'})
    content = get_graphql_content(response)
    assert 'errors' not in content
    product_data = content['data']['products']['edges'][0]['node']
    assert product_data['name'] == product.name


def test_fetch_product_by_id(client, product):
    query = '''
    query ($productId: ID!) {
        node(id: $productId) {
            ... on Product {
                name
            }
        }
    }
    '''
    response = client.post(
        reverse('api'),
        {
            'query': query,
            'variables': json.dumps(
                {
                    'productId': graphene.Node.to_global_id(
                        'Product', product.id)})})
    content = get_graphql_content(response)
    assert 'errors' not in content
    product_data = content['data']['node']
    assert product_data['name'] == product.name


def test_filter_product_by_attributes(client, product):
    product_attr = product.product_type.product_attributes.first()
    category = product.category
    attr_value = product_attr.values.first()
    filter_by = '%s:%s' % (product_attr.slug, attr_value.slug)
    query = '''
    query {
        category(id: "%(category_id)s") {
            products(attributes: ["%(filter_by)s"]) {
                edges {
                    node {
                        name
                    }
                }
            }
        }
    }
    ''' % {
        'category_id': graphene.Node.to_global_id('Category', category.id),
        'filter_by': filter_by}
    response = client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    product_data = content['data']['category']['products']['edges'][0]['node']
    assert product_data['name'] == product.name


def test_sort_products(client, product):
    # set price of the first product
    product.price = Money('10.00', 'USD')
    product.save()

    # create the second product with higher price
    product.pk = None
    product.price = Money('20.00', 'USD')
    product.save()

    query = '''
    query {
        products(sortBy: "%(sort_by)s") {
            edges {
                node {
                    price {
                        amount
                    }
                }
            }
        }
    }
    '''

    asc_price_query = query % {'sort_by': 'price'}
    response = client.post(reverse('api'), {'query': asc_price_query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    product_data = content['data']['products']['edges'][0]['node']
    price_0 = content['data']['products']['edges'][0]['node']['price']['amount']
    price_1 = content['data']['products']['edges'][1]['node']['price']['amount']
    assert price_0 < price_1

    desc_price_query = query % {'sort_by': '-price'}
    response = client.post(reverse('api'), {'query': desc_price_query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    product_data = content['data']['products']['edges'][0]['node']
    price_0 = content['data']['products']['edges'][0]['node']['price']['amount']
    price_1 = content['data']['products']['edges'][1]['node']['price']['amount']
    assert price_0 > price_1


def test_attributes_query(client, product):
    attributes = ProductAttribute.objects.prefetch_related('values')
    query = '''
    query {
        attributes {
            edges {
                node {
                    id
                    name
                    slug
                    values {
                        id
                        name
                        slug
                    }
                }
            }
        }
    }
    '''
    response = client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    attributes_data = content['data']['attributes']['edges']
    assert len(attributes_data) == attributes.count()


def test_attributes_in_category_query(client, product):
    category = Category.objects.first()
    query = '''
    query {
        attributes(inCategory: "%(category_id)s") {
            edges {
                node {
                    id
                    name
                    slug
                    values {
                        id
                        name
                        slug
                    }
                }
            }
        }
    }
    ''' % {'category_id': graphene.Node.to_global_id('Category', category.id)}
    response = client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    attributes_data = content['data']['attributes']['edges']
    assert len(attributes_data) == ProductAttribute.objects.count()


def test_real_query(admin_client, product):
    product_attr = product.product_type.product_attributes.first()
    category = product.category
    attr_value = product_attr.values.first()
    filter_by = '%s:%s' % (product_attr.slug, attr_value.slug)
    query = '''
    query Root($categoryId: ID!, $sortBy: String, $first: Int, $attributesFilter: [AttributeScalar], $minPrice: Float, $maxPrice: Float) {
        category(id: $categoryId) {
            ...CategoryPageFragmentQuery
            __typename
        }
        attributes(inCategory: $categoryId) {
            edges {
                node {
                    ...ProductFiltersFragmentQuery
                    __typename
                }
            }
        }
    }

    fragment CategoryPageFragmentQuery on Category {
        id
        name
        url
        ancestors {
            edges {
                node {
                    name
                    id
                    url
                    __typename
                }
            }
        }
        children {
            edges {
                node {
                    name
                    id
                    url
                    slug
                    __typename
                }
            }
        }
        products(first: $first, sortBy: $sortBy, attributes: $attributesFilter, price_Gte: $minPrice, price_Lte: $maxPrice) {
            ...ProductListFragmentQuery
            __typename
        }
        __typename
    }

    fragment ProductListFragmentQuery on ProductCountableConnection {
        edges {
            node {
                ...ProductFragmentQuery
                __typename
            }
            __typename
        }
        pageInfo {
            hasNextPage
            __typename
        }
        __typename
    }

    fragment ProductFragmentQuery on Product {
        id
        name
        price {
            amount
            currency
            localized
            __typename
        }
        availability {
            ...ProductPriceFragmentQuery
            __typename
        }
        thumbnailUrl1x: thumbnailUrl(size: "255x255")
        thumbnailUrl2x: thumbnailUrl(size: "510x510")
        url
        __typename
    }

    fragment ProductPriceFragmentQuery on ProductAvailability {
        available
        discount {
            gross {
                amount
                currency
                __typename
            }
            __typename
        }
        priceRange {
            stop {
                gross {
                    amount
                    currency
                    localized
                    __typename
                }
                currency
                __typename
            }
            start {
                gross {
                    amount
                    currency
                    localized
                    __typename
                }
                currency
                __typename
            }
            __typename
        }
        __typename
    }

    fragment ProductFiltersFragmentQuery on ProductAttribute {
        id
        name
        slug
        values {
            id
            name
            slug
            __typename
        }
        __typename
    }
    '''
    response = admin_client.post(
        reverse('api'), {
            'query': query,
            'variables': json.dumps(
                {
                    'categoryId': graphene.Node.to_global_id(
                        'Category', category.id),
                    'sortBy': 'name',
                    'first': 1,
                    'attributesFilter': [filter_by]})})
    content = get_graphql_content(response)
    assert 'errors' not in content

def test_page_query(client, page):
    page.is_visible = True
    query = """
    query PageQuery($id: ID!) {
        page(id: $id) {
            title
            slug
        }
    }
    """
    variables = json.dumps({
        'id': graphene.Node.to_global_id('Page', page.id)})
    response = client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    page_data = content['data']['page']
    assert page_data['title'] == page.title
    assert page_data['slug'] == page.slug


def test_paginate_pages(client, page):
    page.is_visible = True
    data_02 = {
        'slug': 'test02-url',
        'title': 'Test page',
        'content': 'test content',
        'is_visible': True}
    data_03 = {
        'slug': 'test03-url',
        'title': 'Test page',
        'content': 'test content',
        'is_visible': True}

    page2 = Page.objects.create(**data_02)
    page3 = Page.objects.create(**data_03)
    query = """
        query PagesQuery {
            pages(first: 2) {
                edges {
                    node {
                        id
                        title
                    }
                }
            }
        }
        """
    response = client.post(
        reverse('api'), {'query': query})
    content = get_graphql_content(response)
    assert 'errors' not in content
    pages_data = content['data']['pages']
    assert len(pages_data['edges']) == 2

@patch('saleor.graphql.core.mutations.convert_form_fields')
@patch('saleor.graphql.core.mutations.convert_form_field')
def test_model_form_mutation(
        mocked_convert_form_field, mocked_convert_form_fields,
        model_form_class):

    mocked_convert_form_fields.return_value = {
        model_form_class._meta.fields: mocked_convert_form_field.return_value}

    class TestMutation(ModelFormMutation):
        test_field = graphene.String()

        class Arguments:
            test_input = graphene.String()

        class Meta:
            form_class = model_form_class
            return_field_name = 'test_return_field'

    meta = TestMutation._meta
    assert meta.form_class == model_form_class
    assert meta.model == 'test_model'
    assert meta.return_field_name == 'test_return_field'
    arguments = meta.arguments
    # check if declarative arguments are present
    assert 'test_input' in arguments
    # check if model form field is present
    mocked_convert_form_fields.assert_called_with(model_form_class, None)
    assert 'test_field' in arguments

    output_fields = meta.fields
    assert 'test_return_field' in output_fields
    assert 'errors' in output_fields


@patch('saleor.graphql.core.mutations')
def test_model_form_update_mutation(model_form_class):
    class TestUpdateMutation(ModelFormUpdateMutation):
        class Meta:
            form_class = model_form_class
            return_field_name = 'test_return_field'

    meta = TestUpdateMutation._meta
    assert 'id' in meta.arguments


def test_create_product(
        admin_client, product_type, default_category, size_attribute):
    query = """
        mutation createProduct(
            $productTypeId: ID!,
            $categoryId: ID!
            $name: String!,
            $description: String!,
            $isPublished: Boolean!,
            $isFeatured: Boolean!,
            $chargeTaxes: Boolean!,
            $taxRate: String!,
            $price: Float!,
            $attributes: [AttributeValueInput]) {
                productCreate(
                    categoryId: $categoryId,
                    productTypeId: $productTypeId,
                    name: $name,
                    description: $description,
                    isPublished: $isPublished,
                    isFeatured: $isFeatured,
                    chargeTaxes: $chargeTaxes,
                    taxRate: $taxRate,
                    price: $price,
                    attributes: $attributes) {
                        product {
                            category{
                                name
                            }
                            description
                            isPublished
                            isFeatured
                            chargeTaxes
                            taxRate
                            name
                            price{
                                amount
                            }
                            productType{
                                name
                            }
                            attributes{
                                name
                                value
                            }
                          }
                          errors {
                            message
                            field
                          }
                        }
                      }
    """

    product_type_id = graphene.Node.to_global_id(
        'ProductType', product_type.pk)
    category_id = graphene.Node.to_global_id(
        'Category', default_category.pk)
    product_description = 'test description'
    product_name = 'test name'
    product_isPublished = True
    product_isFeatured = False
    product_chargeTaxes = True
    product_taxRate = 'standard'
    product_price = 22

    # Default attribute defined in product_type fixture
    color_attr = product_type.product_attributes.get(name='Color')
    color_attr_value = color_attr.values.first().name
    color_value_slug = color_attr.values.first().slug
    color_attr_slug = color_attr.slug
    # Add second attribute
    product_type.product_attributes.add(size_attribute)
    size_attr_slug = product_type.product_attributes.get(name='Size').slug
    non_existent_attr_value = 'The cake is a lie'

    # test creating root product
    variables = json.dumps({
        'productTypeId': product_type_id,
        'categoryId': category_id,
        'name': product_name,
        'description': product_description,
        'isPublished': product_isPublished,
        'isFeatured': product_isFeatured,
        'chargeTaxes': product_chargeTaxes,
        'taxRate': product_taxRate,
        'price': product_price,
        'attributes': [
            {'slug': color_attr_slug, 'value': color_attr_value},
            {'slug': size_attr_slug, 'value': non_existent_attr_value}]})

    response = admin_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['productCreate']
    assert data['errors'] == []
    assert data['product']['name'] == product_name
    assert data['product']['description'] == product_description
    assert data['product']['isFeatured'] == product_isFeatured
    assert data['product']['isPublished'] == product_isPublished
    assert data['product']['chargeTaxes'] == product_chargeTaxes
    assert data['product']['taxRate'] == product_taxRate
    assert data['product']['productType']['name'] == product_type.name
    assert data['product']['category']['name'] == default_category.name
    values = (
        data['product']['attributes'][0].get('value'),
        data['product']['attributes'][1].get('value'))
    assert slugify(non_existent_attr_value) in values
    assert color_value_slug in values


def test_update_product(
        admin_client, default_category, non_default_category,
        product):
    query = """
        mutation updateProduct(
            $productId: ID!,
            $categoryId: ID,
            $name: String!,
            $description: String!,
            $isPublished: Boolean!,
            $isFeatured: Boolean!,
            $chargeTaxes: Boolean!,
            $taxRate: String!,
            $price: Float!,
            $attributes: [AttributeValueInput]) {
                productUpdate(
                    categoryId: $categoryId,
                    id: $productId,
                    name: $name,
                    description: $description,
                    isPublished: $isPublished,
                    isFeatured: $isFeatured,
                    chargeTaxes: $chargeTaxes,
                    taxRate: $taxRate,
                    price: $price,
                    attributes: $attributes) {
                        product {
                            category{
                                name
                            }
                            description
                            isPublished
                            isFeatured
                            chargeTaxes
                            taxRate
                            name
                            price{
                                amount
                            }
                            productType{
                                name
                            }
                            attributes{
                                name
                                value
                            }
                          }
                          errors {
                            message
                            field
                          }
                        }
                      }
    """
    product_id = graphene.Node.to_global_id('Product', product.pk)
    category_id = graphene.Node.to_global_id(
        'Category', non_default_category.pk)
    product_description = 'updated description'
    product_name = 'updated name'
    product_isPublished = True
    product_isFeatured = False
    product_chargeTaxes = True
    product_taxRate = 'standard'
    product_price = 33

    variables = json.dumps({
        'productId': product_id,
        'categoryId': category_id,
        'name': product_name,
        'description': product_description,
        'isPublished': product_isPublished,
        'isFeatured': product_isFeatured,
        'chargeTaxes': product_chargeTaxes,
        'taxRate': product_taxRate,
        'price': product_price})

    response = admin_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['productUpdate']
    assert data['errors'] == []
    assert data['product']['name'] == product_name
    assert data['product']['description'] == product_description
    assert data['product']['isFeatured'] == product_isFeatured
    assert data['product']['isPublished'] == product_isPublished
    assert data['product']['chargeTaxes'] == product_chargeTaxes
    assert data['product']['taxRate'] == product_taxRate
    assert not data['product']['category']['name'] == default_category.name


def test_delete_product(admin_client, product):
    query = """
        mutation DeleteProduct($id: ID!) {
            productDelete(id: $id) {
                product {
                    name
                    id
                }
                errors {
                    field
                    message
                }
              }
            }
    """
    variables = json.dumps({
        'id': graphene.Node.to_global_id('Product', product.id)})
    response = admin_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['productDelete']
    assert data['product']['name'] == product.name
    with pytest.raises(product._meta.model.DoesNotExist):
        product.refresh_from_db()


def test_category_create_mutation(admin_client):
    query = """
        mutation($name: String!, $description: String, $parentId: ID) {
            categoryCreate(
                name: $name
                description: $description
                parentId: $parentId
            ) {
                category {
                    id
                    name
                    slug
                    description
                    parent {
                        name
                        id
                    }
                }
                errors {
                    field
                    message
                }
            }
        }
    """

    category_name = 'Test category'
    category_description = 'Test description'

    # test creating root category
    variables = json.dumps({
        'name': category_name, 'description': category_description})
    response = admin_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['categoryCreate']
    assert data['errors'] == []
    assert data['category']['name'] == category_name
    assert data['category']['description'] == category_description
    assert not data['category']['parent']

    # test creating subcategory
    parent_id = data['category']['id']
    variables = json.dumps({
        'name': category_name, 'description': category_description,
        'parentId': parent_id})
    response = admin_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['categoryCreate']
    assert data['errors'] == []
    assert data['category']['parent']['id'] == parent_id


def test_category_update_mutation(admin_client, default_category):
    query = """
        mutation($id: ID, $name: String!, $description: String) {
            categoryUpdate(
                id: $id
                name: $name
                description: $description
            ) {
                category {
                    id
                    name
                    description
                    parent {
                        id
                    }
                }
                errors {
                    field
                    message
                }
            }
        }
    """
    # create child category and test that the update mutation won't change
    # it's parent
    child_category = default_category.children.create(name='child')

    category_name = 'Updated name'
    category_description = 'Updated description'

    category_id = graphene.Node.to_global_id('Category', child_category.pk)
    variables = json.dumps({
        'name': category_name, 'description': category_description,
        'id': category_id})
    response = admin_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['categoryUpdate']
    assert data['errors'] == []
    assert data['category']['id'] == category_id
    assert data['category']['name'] == category_name
    assert data['category']['description'] == category_description

    parent_id = graphene.Node.to_global_id('Category', default_category.pk)
    assert data['category']['parent']['id'] == parent_id


def test_category_delete_mutation(admin_client, default_category):
    query = """
        mutation($id: ID!) {
            categoryDelete(id: $id) {
                category {
                    name
                }
                errors {
                    field
                    message
                }
            }
        }
    """
    variables = json.dumps({
        'id': graphene.Node.to_global_id('Category', default_category.id)})
    response = admin_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['categoryDelete']
    assert data['category']['name'] == default_category.name
    with pytest.raises(default_category._meta.model.DoesNotExist):
        default_category.refresh_from_db()


def test_page_create_mutation(admin_client):
    query = """
        mutation CreatePage(
            $slug: String!,
            $title: String!,
            $content: String!,
            $isVisible: Boolean!) {
                pageCreate(slug: $slug,
                title: $title,
                content: $content,
                isVisible: $isVisible) {
                    page {
                        id
                        title
                        content
                        slug
                        isVisible
                      }
                      errors {
                        message
                        field
                      }
                    }
                  }
    """
    page_slug = 'test-slug'
    page_content = 'test content'
    page_title = 'test title'
    page_isVisible = True

    # test creating root page
    variables = json.dumps({
        'title': page_title, 'content': page_content,
        'isVisible': page_isVisible, 'slug': page_slug})
    response = admin_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['pageCreate']
    assert data['errors'] == []
    assert data['page']['title'] == page_title
    assert data['page']['content'] == page_content
    assert data['page']['slug'] == page_slug
    assert data['page']['isVisible'] == page_isVisible


def test_page_delete_mutation(admin_client, page):
    query = """
        mutation DeletePage($id: ID!) {
            pageDelete(id: $id) {
                page {
                    title
                    id
                }
                errors {
                    field
                    message
                }
              }
            }
    """
    variables = json.dumps({
        'id': graphene.Node.to_global_id('Page', page.id)})
    response = admin_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['pageDelete']
    assert data['page']['title'] == page.title
    with pytest.raises(page._meta.model.DoesNotExist):
        page.refresh_from_db()


def test_product_type(client, product_type):
    query = """
    query {
        productTypes {
            totalCount
            edges {
                node {
                    id
                    name
                }
            }
        }
    }
    """
    response = client.post(reverse('api'), {'query': query})
    content = get_graphql_content(response)
    no_product_types = ProductType.objects.count()
    assert 'errors' not in content
    assert content['data']['productTypes']['totalCount'] == no_product_types
    assert len(content['data']['productTypes']['edges']) == no_product_types


def test_product_type_query(
        client, admin_client, product_type, product):
    query = """
            query getProductType($id: ID!) {
                productType(id: $id) {
                    name
                    products {
                        totalCount
                        edges{
                            node{
                                name
                            }
                        }
                    }
                }
            }
        """
    no_products = Product.objects.count()
    product.is_published = False
    product.save()
    variables = json.dumps({
        'id': graphene.Node.to_global_id('ProductType', product_type.id)})

    response = client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']
    assert data['productType']['products']['totalCount'] == no_products - 1

    response = admin_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']
    assert data['productType']['products']['totalCount'] == no_products


def test_product_type_create_mutation(admin_client, product_type):
    query = """
    mutation createProductType(
        $name: String!,
        $hasVariants: Boolean!,
        $isShippingRequired: Boolean!,
        $productAttributes: [ID],
        $variantAttributes: [ID]) {
            productTypeCreate(
            name: $name,
            hasVariants: $hasVariants,
            isShippingRequired: $isShippingRequired,
            productAttributes: $productAttributes,
            variantAttributes: $variantAttributes) {
                productType {
                    name
                    isShippingRequired
                    hasVariants
                    variantAttributes {
                        edges {
                            node {
                                name
                            }
                        }
                    }
                    productAttributes {
                        edges {
                            node {
                                name
                            }
                        }
                    }
                }
              }
            }
    """
    product_type_name = 'test type'
    has_variants = True
    require_shipping = True
    product_attributes = product_type.product_attributes.all()
    product_attributes_ids = [
        graphene.Node.to_global_id('ProductAttribute', att.id) for att in
        product_attributes]
    variant_attributes = product_type.variant_attributes.all()
    variant_attributes_ids = [
        graphene.Node.to_global_id('ProductAttribute', att.id) for att in
        variant_attributes]

    variables = json.dumps({
        'name': product_type_name, 'hasVariants': has_variants,
        'isShippingRequired': require_shipping,
        'productAttributes': product_attributes_ids,
        'variantAttributes': variant_attributes_ids})
    response = admin_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['productTypeCreate']
    assert data['productType']['name'] == product_type_name
    assert data['productType']['hasVariants'] == has_variants
    assert data['productType']['isShippingRequired'] == require_shipping
    no_pa = product_attributes.count()
    assert len(data['productType']['productAttributes']['edges']) == no_pa
    no_va = variant_attributes.count()
    assert len(data['productType']['variantAttributes']['edges']) == no_va


def test_product_type_update_mutation(admin_client, product_type):
    query = """
    mutation updateProductType(
        $id: ID!,
        $name: String!,
        $hasVariants: Boolean!,
        $isShippingRequired: Boolean!,
        $productAttributes: [ID],
        ) {
            productTypeUpdate(
            id: $id,
            name: $name,
            hasVariants: $hasVariants,
            isShippingRequired: $isShippingRequired,
            productAttributes: $productAttributes) {
                productType {
                    name
                    isShippingRequired
                    hasVariants
                    variantAttributes {
                        edges {
                            node {
                                name
                            }
                        }
                    }
                    productAttributes {
                        edges {
                            node {
                                name
                            }
                        }
                    }
                }
              }
            }
    """
    product_type_name = 'test type updated'
    has_variants = True
    require_shipping = False
    product_type_id = graphene.Node.to_global_id(
        'ProductType', product_type.id)

    # Test scenario: remove all product attributes using [] as input
    # but do not change variant attributes
    product_attributes = []
    product_attributes_ids = [
        graphene.Node.to_global_id('ProductAttribute', att.id) for att in
        product_attributes]
    variant_attributes = product_type.variant_attributes.all()

    variables = json.dumps({
        'id': product_type_id, 'name': product_type_name,
        'hasVariants': has_variants,
        'isShippingRequired': require_shipping,
        'productAttributes': product_attributes_ids})
    response = admin_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['productTypeUpdate']
    assert data['productType']['name'] == product_type_name
    assert data['productType']['hasVariants'] == has_variants
    assert data['productType']['isShippingRequired'] == require_shipping
    assert len(data['productType']['productAttributes']['edges']) == 0
    no_va = variant_attributes.count()
    assert len(data['productType']['variantAttributes']['edges']) == no_va


def test_product_type_delete_mutation(admin_client, product_type):
    query = """
        mutation deleteProductType($id: ID!) {
            productTypeDelete(id: $id) {
                productType {
                    name
                }
            }
        }
    """
    variables = json.dumps({
        'id': graphene.Node.to_global_id('ProductType', product_type.id)})
    response = admin_client.post(
        reverse('api'), {'query': query, 'variables': variables})
    content = get_graphql_content(response)
    assert 'errors' not in content
    data = content['data']['productTypeDelete']
    assert data['productType']['name'] == product_type.name
    with pytest.raises(product_type._meta.model.DoesNotExist):
        product_type.refresh_from_db()
