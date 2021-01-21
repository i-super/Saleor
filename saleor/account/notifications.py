from urllib.parse import urlencode

from django.contrib.auth.tokens import default_token_generator

from ..core.notifications import get_site_context
from ..core.notify_events import NotifyEventType
from ..core.utils.url import prepare_url
from .models import User


def get_default_user_payload(user: User):
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_staff": user.is_staff,
        "is_active": user.is_active,
        "private_metadata": user.private_metadata,
        "metadata": user.metadata,
        "language_code": user.language_code,
    }


def send_user_password_reset_notification(redirect_url, user, manager):
    """Trigger sending a password reset notification for the given user."""
    token = default_token_generator.make_token(user)
    params = urlencode({"email": user.email, "token": token})
    reset_url = prepare_url(params, redirect_url)

    user_payload = {
        "user": get_default_user_payload(user),
        "recipient_email": user.email,
        "token": token,
        "reset_url": reset_url,
        **get_site_context(),
    }
    manager.notify(NotifyEventType.ACCOUNT_PASSWORD_RESET, payload=user_payload)


def send_account_confirmation(user, redirect_url, manager):
    """Trigger sending an account confirmation notification for the given user."""
    token = default_token_generator.make_token(user)
    params = urlencode({"email": user.email, "token": token})
    confirm_url = prepare_url(params, redirect_url)
    payload = {
        "user": get_default_user_payload(user),
        "recipient_email": user.email,
        "token": default_token_generator.make_token(user),
        "confirm_url": confirm_url,
        **get_site_context(),
    }
    manager.notify(NotifyEventType.ACCOUNT_CONFIRMATION, payload=payload)


def send_request_user_change_email_notification(
    redirect_url, user, new_email, token, manager
):
    """Trigger sending a notification change email for the given user."""
    params = urlencode({"token": token})
    redirect_url = prepare_url(params, redirect_url)
    payload = {
        "user": get_default_user_payload(user),
        "recipient_email": new_email,
        "old_email": user.email,
        "new_email": new_email,
        "token": token,
        "redirect_url": redirect_url,
        **get_site_context(),
    }
    manager.notify(NotifyEventType.ACCOUNT_CHANGE_EMAIL_REQUEST, payload=payload)


def send_user_change_email_notification(recipient_email, user, manager):
    """Trigger sending a email change notification for the given user."""
    payload = {
        "user": get_default_user_payload(user),
        "recipient_email": recipient_email,
        **get_site_context(),
    }
    manager.notify(NotifyEventType.ACCOUNT_CHANGE_EMAIL_CONFIRM, payload=payload)


def send_account_delete_confirmation_notification(redirect_url, user, manager):
    """Trigger sending a account delete notification for the given user."""
    token = default_token_generator.make_token(user)
    params = urlencode({"token": token})
    delete_url = prepare_url(params, redirect_url)
    payload = {
        "user": get_default_user_payload(user),
        "recipient_email": user.email,
        "token": token,
        "delete_url": delete_url,
        **get_site_context(),
    }
    manager.notify(NotifyEventType.ACCOUNT_DELETE, payload=payload)


def send_set_password_notification(redirect_url, user, manager, staff=False):
    """Trigger sending a set password notification for the given customer/staff."""
    token = default_token_generator.make_token(user)
    params = urlencode({"email": user.email, "token": token})
    password_set_url = prepare_url(params, redirect_url)
    user_payload = {
        "user": get_default_user_payload(user),
        "token": default_token_generator.make_token(user),
        "recipient_email": user.email,
        "password_set_url": password_set_url,
        **get_site_context(),
    }
    if staff:
        event = NotifyEventType.ACCOUNT_SET_STAFF_PASSWORD
    else:
        event = NotifyEventType.ACCOUNT_SET_CUSTOMER_PASSWORD
    manager.notify(event, payload=user_payload)
