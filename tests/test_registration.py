from django.shortcuts import reverse
from django.contrib.auth.models import AnonymousUser

from saleor.userprofile.registration.forms import LoginForm
from .utils import get_redirect_location


def test_login_form_valid(customer_user):
    data = {'username': 'test@example.com', 'password': 'password'}
    form = LoginForm(data=data)
    assert form.is_valid()
    assert form.get_user() == customer_user


def test_login_form_not_valid(customer_user):
    data = {'user': 'test@example.com', 'password': 'wrongpassword'}
    form = LoginForm(data=data)
    assert not form.is_valid()
    assert form.get_user_id() is None


def test_login_view_valid(client, customer_user):
    url = reverse('account_login')
    response = client.post(
        url, {'username': 'test@example.com', 'password': 'password'},
        follow=True)
    assert response.context['user'] == customer_user


def test_login_view_not_valid(client, customer_user):
    url = reverse('account_login')
    response = client.post(
        url, {'username': 'test@example.com', 'password': 'wrong'},
        follow=True)
    assert isinstance(response.context['user'], AnonymousUser)


def test_login_view_next(client, customer_user):
    url = reverse('account_login') + '?next=/cart/'
    response = client.post(
        url, {'username': 'test@example.com', 'password': 'password'})
    redirect_location = get_redirect_location(response)
    assert redirect_location == '/cart/'


def test_logout_view_no_user(client):
    url = reverse('account_logout')
    response = client.get(url)
    redirect_location = get_redirect_location(response)
    location = '/account/login/?next=/account/logout'
    assert redirect_location == location


def test_logout_with_user(authorized_client):
    url = reverse('account_logout')
    response = authorized_client.get(url, follow=True)
    assert isinstance(response.context['user'], AnonymousUser)
