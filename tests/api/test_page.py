import pytest

import graphene
from saleor.page.models import Page
from tests.api.utils import get_graphql_content


def test_page_query(user_api_client, page):
    page.is_visible = True
    query = """
    query PageQuery($id: ID!) {
        page(id: $id) {
            title
            slug
        }
    }
    """
    variables = {'id': graphene.Node.to_global_id('Page', page.id)}
    response = user_api_client.post_graphql(query, variables)
    content = get_graphql_content(response)
    page_data = content['data']['page']
    assert page_data['title'] == page.title
    assert page_data['slug'] == page.slug


def test_page_create_mutation(staff_api_client, permission_manage_pages):
    query = """
        mutation CreatePage(
                $slug: String!, $title: String!, $content: String!,
                $isVisible: Boolean!) {
            pageCreate(
                    input: {
                        slug: $slug, title: $title,
                        content: $content, isVisible: $isVisible}) {
                page {
                    id
                    title
                    content
                    slug
                    isVisible
                }
                errors {
                    field
                    message
                }
            }
        }
    """
    page_slug = 'test-slug'
    page_content = 'test content'
    page_title = 'test title'
    page_isVisible = True

    # test creating root page
    variables = {
        'title': page_title, 'content': page_content,
        'isVisible': page_isVisible, 'slug': page_slug}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_pages])
    content = get_graphql_content(response)
    data = content['data']['pageCreate']
    assert data['errors'] == []
    assert data['page']['title'] == page_title
    assert data['page']['content'] == page_content
    assert data['page']['slug'] == page_slug
    assert data['page']['isVisible'] == page_isVisible


def test_page_delete_mutation(staff_api_client, page, permission_manage_pages):
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
    variables = {'id': graphene.Node.to_global_id('Page', page.id)}
    response = staff_api_client.post_graphql(
        query, variables, permissions=[permission_manage_pages])
    content = get_graphql_content(response)
    data = content['data']['pageDelete']
    assert data['page']['title'] == page.title
    with pytest.raises(page._meta.model.DoesNotExist):
        page.refresh_from_db()


def test_paginate_pages(user_api_client, page):
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
    response = user_api_client.post_graphql(query)
    content = get_graphql_content(response)
    pages_data = content['data']['pages']
    assert len(pages_data['edges']) == 2
