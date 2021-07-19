import json
import logging
from enum import Enum
from json import JSONDecodeError
from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

import boto3
import requests
from celery.utils.log import get_task_logger
from google.cloud import pubsub_v1
from requests.exceptions import RequestException

from ...celeryconf import app
from ...core.models import EventPayload, EventTask, JobStatus
from ...payment import PaymentError
from ...site.models import Site
from ...webhook.event_types import WebhookEventType
from ...webhook.models import Webhook
from . import signature_for_payload
from .utils import catch_duration_time

if TYPE_CHECKING:
    from ...app.models import App

logger = logging.getLogger(__name__)
task_logger = get_task_logger(__name__)

WEBHOOK_TIMEOUT = 10


class WebhookSchemes(str, Enum):
    HTTP = "http"
    HTTPS = "https"
    AWS_SQS = "awssqs"
    GOOGLE_CLOUD_PUBSUB = "gcpubsub"


@app.task(compression="zlib")
def _get_webhooks_for_event(event_type, webhooks=None):
    """Get active webhooks from the database for an event."""
    permissions = {}
    required_permission = WebhookEventType.PERMISSIONS.get(event_type)
    if required_permission:
        app_label, codename = required_permission.value.split(".")
        permissions["app__permissions__content_type__app_label"] = app_label
        permissions["app__permissions__codename"] = codename

    if webhooks is None:
        webhooks = Webhook.objects.all()

    webhooks = webhooks.filter(
        is_active=True,
        app__is_active=True,
        events__event_type__in=[event_type, WebhookEventType.ANY],
        **permissions,
    )
    webhooks = webhooks.select_related("app").prefetch_related(
        "app__permissions__content_type"
    )
    return webhooks


@app.task
def trigger_webhooks_for_event(event_type, event_payload_id):
    """Send a webhook request for an event as an async task."""
    webhooks = _get_webhooks_for_event(event_type)
    for webhook in webhooks:
        send_webhook_request.delay(
            webhook.pk,
            webhook.target_url,
            webhook.secret_key,
            event_type,
            event_payload_id,
        )


def trigger_webhook_sync(event_type: str, data: str, app: "App"):
    """Send a synchronous webhook request."""
    webhooks = _get_webhooks_for_event(event_type, app.webhooks.all())
    webhook = webhooks.first()
    if not webhook:
        raise PaymentError(f"No payment webhook found for event: {event_type}.")

    return send_webhook_request_sync(
        webhook.target_url, webhook.secret_key, event_type, data
    )


def send_webhook_using_http(target_url, message, domain, signature, event_type):
    headers = {
        "Content-Type": "application/json",
        "X-Saleor-Event": event_type,
        "X-Saleor-Domain": domain,
        "X-Saleor-Signature": signature,
    }

    response = requests.post(
        target_url, data=message, headers=headers, timeout=WEBHOOK_TIMEOUT
    )
    response.raise_for_status()
    return response


def send_webhook_using_aws_sqs(target_url, message, domain, signature, event_type):
    parts = urlparse(target_url)
    region = "us-east-1"
    hostname_parts = parts.hostname.split(".")
    if len(hostname_parts) == 4 and hostname_parts[0] == "sqs":
        region = hostname_parts[1]
    client = boto3.client(
        "sqs",
        region_name=region,
        aws_access_key_id=parts.username,
        aws_secret_access_key=parts.password,
    )
    queue_url = urlunparse(
        ("https", parts.hostname, parts.path, parts.params, parts.query, parts.fragment)
    )
    is_fifo = parts.path.endswith(".fifo")

    msg_attributes = {
        "SaleorDomain": {"DataType": "String", "StringValue": domain},
        "EventType": {"DataType": "String", "StringValue": event_type},
    }
    if signature:
        msg_attributes["Signature"] = {"DataType": "String", "StringValue": signature}

    message_kwargs = {
        "QueueUrl": queue_url,
        "MessageAttributes": msg_attributes,
        "MessageBody": message.decode("utf-8"),
    }
    if is_fifo:
        message_kwargs["MessageGroupId"] = domain
    client.send_message(**message_kwargs)


def send_webhook_using_google_cloud_pubsub(
    target_url, message, domain, signature, event_type
):
    parts = urlparse(target_url)
    client = pubsub_v1.PublisherClient()
    topic_name = parts.path[1:]  # drop the leading slash
    client.publish(
        topic_name,
        message,
        saleorDomain=domain,
        eventType=event_type,
        signature=signature,
    )


def _send_webhook_to_target(parts, target_url, message, domain, signature, event_type):
    scheme = parts.scheme.lower()
    if scheme in [WebhookSchemes.HTTP, WebhookSchemes.HTTPS]:
        send_webhook_using_http(target_url, message, domain, signature, event_type)
    elif scheme == WebhookSchemes.AWS_SQS:
        send_webhook_using_aws_sqs(target_url, message, domain, signature, event_type)
    elif scheme == WebhookSchemes.GOOGLE_CLOUD_PUBSUB:
        send_webhook_using_google_cloud_pubsub(
            target_url, message, domain, signature, event_type
        )
    else:
        raise ValueError("Unknown webhook scheme: %r" % (parts.scheme,))


def _get_event_payload(task_id, event_payload_id, event_type, webhook_id, target_url):
    try:
        event_payload = EventPayload.objects.get(id=event_payload_id)
        return json.loads(event_payload.payload)
    except EventPayload.DoesNotExist as exc:
        EventTask.objects.create(
            task_id=task_id,
            event_payload_id=event_payload_id,
            status=JobStatus.FAILED,
            error=str(exc),
            duration=0,
            event_type=event_type,
            webhook_id=webhook_id,
        )
        task_logger.error(
            "Cannot find payload related to webhook.",
            extra={
                "webhook_id": webhook_id,
                "event_payload_id": event_payload_id,
                "target_url": target_url,
                "event_type": event_type,
            },
        )
        return None


@app.task(
    bind=True,
    autoretry_for=(RequestException,),
    retry_backoff=10,
    retry_kwargs={"max_retries": 5},
)
def send_webhook_request(
    self, webhook_id, target_url, secret, event_type, event_payload_id
):
    data = _get_event_payload(
        self.request.id, event_payload_id, event_type, webhook_id, target_url
    )
    if not data:
        return
    parts = urlparse(target_url)
    domain = Site.objects.get_current().domain
    message = data.encode("utf-8")
    signature = signature_for_payload(message, secret)
    error = None
    with catch_duration_time() as duration:
        try:
            _send_webhook_to_target(
                parts, target_url, message, domain, signature, event_type
            )
        except Exception as exc:
            error = exc
            raise exc
        finally:
            EventTask.objects.create(
                task_id=self.request.id,
                event_payload_id=event_payload_id,
                status=JobStatus.FAILED if error else JobStatus.SUCCESS,
                error=str(error) if error else None,
                duration=duration().total_seconds(),
                event_type=event_type,
                webhook_id=webhook_id,
            )
    task_logger.debug(
        "[Webhook ID:%r] Payload sent to %r for event %r",
        webhook_id,
        target_url,
        event_type,
    )


def send_webhook_request_sync(target_url, secret, event_type, data: str):
    parts = urlparse(target_url)
    domain = Site.objects.get_current().domain
    message = data.encode("utf-8")
    signature = signature_for_payload(message, secret)

    response_data = None
    if parts.scheme.lower() in [WebhookSchemes.HTTP, WebhookSchemes.HTTPS]:
        logger.debug(
            "[Webhook] Sending payload to %r for event %r.", target_url, event_type
        )
        try:
            response = send_webhook_using_http(
                target_url, message, domain, signature, event_type
            )
            response_data = response.json()
        except RequestException as e:
            logger.debug("[Webhook] Failed request to %r: %r.", target_url, e)
        except JSONDecodeError as e:
            logger.debug(
                "[Webhook] Failed parsing JSON response from %r: %r.", target_url, e
            )
        else:
            logger.debug("[Webhook] Success response from %r.", target_url)
    else:
        raise ValueError("Unknown webhook scheme: %r" % (parts.scheme,))
    return response_data
