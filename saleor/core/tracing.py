from contextlib import contextmanager

import opentracing
from django.db import transaction
from graphql import ResolveInfo


def traced_resolver(func):
    def wrapper(*args, **kwargs):
        info = next(arg for arg in args if isinstance(arg, ResolveInfo))
        operation = f"{info.parent_type.name}.{info.field_name}"
        with opentracing.global_tracer().start_active_span(operation) as scope:
            span = scope.span
            span.set_tag(opentracing.tags.COMPONENT, "graphql")
            span.set_tag("graphql.parent_type", info.parent_type.name)
            span.set_tag("graphql.field_name", info.field_name)
            return func(*args, **kwargs)

    return wrapper


@contextmanager
def traced_atomic_transaction():
    with transaction.atomic():
        with opentracing.global_tracer().start_active_span("transaction") as scope:
            span = scope.span
            span.set_tag(opentracing.tags.COMPONENT, "orm")
            yield
