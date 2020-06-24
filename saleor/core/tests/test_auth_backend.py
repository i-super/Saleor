import jwt
import pytest
from django.contrib.auth.models import Permission
from freezegun import freeze_time
from jwt import ExpiredSignatureError, InvalidSignatureError

from ..auth_backend import JSONWebTokenBackend
from ..jwt import (
    JWT_ACCESS_TYPE,
    JWT_ALGORITHM,
    create_access_token,
    create_access_token_for_app,
    create_refresh_token,
    jwt_user_payload,
)
from ..permissions import get_permissions_from_names


def test_user_authenticated(rf, staff_user):
    access_token = create_access_token(staff_user)
    request = rf.request(HTTP_AUTHORIZATION=f"JWT {access_token}")
    backend = JSONWebTokenBackend()
    user = backend.authenticate(request)
    assert user == staff_user


def test_user_deactivated(rf, staff_user):
    staff_user.is_active = False
    staff_user.save()
    access_token = create_access_token(staff_user)
    request = rf.request(HTTP_AUTHORIZATION=f"JWT {access_token}")
    backend = JSONWebTokenBackend()
    assert backend.authenticate(request) is None


def test_incorect_type_of_token(rf, staff_user):
    token = create_refresh_token(staff_user)
    request = rf.request(HTTP_AUTHORIZATION=f"JWT {token}")
    backend = JSONWebTokenBackend()
    assert backend.authenticate(request) is None


def test_incorrect_token(rf, staff_user, settings):
    payload = jwt_user_payload(staff_user, JWT_ACCESS_TYPE, settings.JWT_TTL_ACCESS,)
    token = jwt.encode(payload, "Wrong secret", JWT_ALGORITHM,).decode("utf-8")
    request = rf.request(HTTP_AUTHORIZATION=f"JWT {token}")
    backend = JSONWebTokenBackend()
    with pytest.raises(InvalidSignatureError):
        backend.authenticate(request)


def test_missing_token(rf, staff_user):
    request = rf.request(HTTP_AUTHORIZATION="JWT ")
    backend = JSONWebTokenBackend()
    assert backend.authenticate(request) is None


def test_missing_header(rf, staff_user):
    request = rf.request()
    backend = JSONWebTokenBackend()
    assert backend.authenticate(request) is None


def test_token_expired(rf, staff_user):
    with freeze_time("2019-03-18 12:00:00"):
        access_token = create_access_token(staff_user)
    request = rf.request(HTTP_AUTHORIZATION=f"JWT {access_token}")
    backend = JSONWebTokenBackend()
    with pytest.raises(ExpiredSignatureError):
        backend.authenticate(request)


def test_user_doesnt_exist(rf, staff_user):
    access_token = create_access_token(staff_user)
    staff_user.delete()
    request = rf.request(HTTP_AUTHORIZATION=f"JWT {access_token}")
    backend = JSONWebTokenBackend()
    assert backend.authenticate(request) is None


def test_user_deactivated_token(rf, staff_user):
    access_token = create_access_token(staff_user)
    staff_user.jwt_token_key = "New key"
    staff_user.save()
    request = rf.request(HTTP_AUTHORIZATION=f"JWT {access_token}")
    backend = JSONWebTokenBackend()
    assert backend.authenticate(request) is None


@pytest.mark.parametrize(
    "user_permissions, app_permissions, expected_limited_permissions",
    [
        (
            ["manage_apps", "manage_checkouts"],
            ["manage_checkouts"],
            ["MANAGE_CHECKOUTS"],
        ),
        ([], ["manage_checkouts"], []),
        ([], [], []),
        (["manage_apps"], ["manage_checkouts"], []),
        (["manage_checkouts"], [], []),
        (
            ["manage_orders", "manage_checkouts", "manage_apps"],
            ["manage_checkouts", "manage_apps"],
            ["MANAGE_CHECKOUTS", "MANAGE_APPS"],
        ),
    ],
)
def test_user_with_limited_permissions(
    user_permissions, app_permissions, expected_limited_permissions, rf, staff_user, app
):
    staff_user.user_permissions.set(
        Permission.objects.filter(codename__in=user_permissions)
    )
    app.permissions.set(Permission.objects.filter(codename__in=app_permissions))
    access_token_for_app = create_access_token_for_app(app, staff_user)
    request = rf.request(HTTP_AUTHORIZATION=f"JWT {access_token_for_app}")
    backend = JSONWebTokenBackend()
    user = backend.authenticate(request)
    assert user == staff_user
    user_permissions = user.effective_permissions
    limited_permissions = get_permissions_from_names(expected_limited_permissions)
    assert set(user_permissions) == set(limited_permissions)
