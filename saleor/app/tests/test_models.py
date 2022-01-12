from ...app.models import App
from ...webhook.event_types import WebhookEventSyncType


def test_qs_for_event_type(payment_app):
    qs = App.objects.for_event_type(WebhookEventSyncType.PAYMENT_AUTHORIZE)
    assert len(qs) == 1
    assert qs[0] == payment_app


def test_qs_for_event_type_no_payment_permissions(payment_app):
    payment_app.permissions.first().delete()
    qs = App.objects.for_event_type(WebhookEventSyncType.PAYMENT_AUTHORIZE)
    assert len(qs) == 0


def test_qs_for_event_type_inactive_app(payment_app):
    payment_app.is_active = False
    payment_app.save()
    qs = App.objects.for_event_type(WebhookEventSyncType.PAYMENT_AUTHORIZE)
    assert len(qs) == 0


def test_qs_for_event_type_no_webhook_event(payment_app):
    webhook = payment_app.webhooks.first()
    event = webhook.events.filter(
        event_type=WebhookEventSyncType.PAYMENT_AUTHORIZE
    ).first()
    event.delete()
    qs = App.objects.for_event_type(WebhookEventSyncType.PAYMENT_AUTHORIZE)
    assert len(qs) == 0


def test_qs_for_event_type_inactive_webhook(payment_app):
    webhook = payment_app.webhooks.first()
    webhook.is_active = False
    webhook.save()
    qs = App.objects.for_event_type(WebhookEventSyncType.PAYMENT_AUTHORIZE)
    assert len(qs) == 0
