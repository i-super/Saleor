from typing import Optional

import opentracing
import opentracing.tags
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils.functional import SimpleLazyObject
from graphql import ResolveInfo
from graphql_jwt.middleware import JSONWebTokenMiddleware

from ..app.models import App
from ..core.tracing import should_trace
from .views import API_PATH, GraphQLView


class JWTMiddleware(JSONWebTokenMiddleware):
    def resolve(self, next, root, info, **kwargs):
        request = info.context

        if not hasattr(request, "user"):
            request.user = AnonymousUser()
        return super().resolve(next, root, info, **kwargs)


class OpentracingGrapheneMiddleware:
    @staticmethod
    def resolve(next_, root, info: ResolveInfo, **kwargs):
        if not should_trace(info):
            return next_(root, info, **kwargs)
        operation = f"{info.parent_type.name}.{info.field_name}"
        with opentracing.global_tracer().start_active_span(operation) as scope:
            span = scope.span
            span.set_tag(opentracing.tags.COMPONENT, "graphql")
            span.set_tag("graphql.parent_type", info.parent_type.name)
            span.set_tag("graphql.field_name", info.field_name)
            return next_(root, info, **kwargs)


def get_app(auth_token) -> Optional[App]:
    qs = App.objects.filter(tokens__auth_token=auth_token, is_active=True)
    return qs.first()


def app_middleware(next, root, info, **kwargs):

    app_auth_header = "HTTP_AUTHORIZATION"
    prefix = "bearer"
    request = info.context

    if request.path == API_PATH:
        if not hasattr(request, "app"):
            request.app = None
            auth = request.META.get(app_auth_header, "").split()
            if len(auth) == 2:
                auth_prefix, auth_token = auth
                if auth_prefix.lower() == prefix:
                    request.app = SimpleLazyObject(lambda: get_app(auth_token))
    return next(root, info, **kwargs)


def process_view(self, request, view_func, *args):
    if hasattr(view_func, "view_class") and issubclass(
        view_func.view_class, GraphQLView
    ):
        request._graphql_view = True


if settings.ENABLE_DEBUG_TOOLBAR:
    import warnings

    try:
        from graphiql_debug_toolbar.middleware import DebugToolbarMiddleware
    except ImportError:
        warnings.warn("The graphiql debug toolbar was not installed.")
    else:
        DebugToolbarMiddleware.process_view = process_view
