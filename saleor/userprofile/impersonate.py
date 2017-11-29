# Module used to config django-impersonate app
from __future__ import unicode_literals

from .models import User


def get_impersonatable_users(request):
    '''
    Returns QuerySet containing all .models.User(s) that can be impersonated
    '''
    return User.objects.filter(is_staff=False, is_superuser=False)


def can_impersonate(request):
    '''Checks if user has right permissions to impersonate customers;
    django-impersonate module requires a function as input argument,
    not just permission name.
    '''
    return request.user.has_perm('userprofile.impersonate_user')
