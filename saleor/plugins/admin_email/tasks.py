from ...celeryconf import app
from ...csv.events import export_failed_info_sent_event, export_file_sent_event
from ..email_common import (
    EmailConfig,
    get_email_subject,
    get_email_template_or_default,
    send_email,
)
from . import constants


@app.task
def send_set_staff_password_email_task(recipient_email, payload, config: dict):
    email_config = EmailConfig(**config)
    email_template_str = get_email_template_or_default(
        constants.PLUGIN_ID,
        constants.SET_STAFF_PASSWORD_TEMPLATE_FIELD,
        constants.SET_STAFF_PASSWORD_DEFAULT_TEMPLATE,
    )
    subject = get_email_subject(
        constants.PLUGIN_ID,
        constants.SET_STAFF_PASSWORD_SUBJECT_FIELD,
        constants.SET_STAFF_PASSWORD_DEFAULT_SUBJECT,
    )
    send_email(
        config=email_config,
        recipient_list=[recipient_email],
        context=payload,
        subject=subject,
        template_str=email_template_str,
    )


@app.task
def send_email_with_link_to_download_file_task(
    recipient_email: str, payload, config: dict
):
    email_config = EmailConfig(**config)
    email_template_str = get_email_template_or_default(
        constants.PLUGIN_ID,
        constants.CSV_PRODUCT_EXPORT_SUCCESS_TEMPLATE_FIELD,
        constants.CSV_PRODUCT_EXPORT_SUCCESS_DEFAULT_TEMPLATE,
    )
    subject = get_email_subject(
        constants.PLUGIN_ID,
        constants.CSV_PRODUCT_EXPORT_SUCCESS_SUBJECT_FIELD,
        constants.CSV_PRODUCT_EXPORT_SUCCESS_DEFAULT_SUBJECT,
    )
    send_email(
        config=email_config,
        recipient_list=[recipient_email],
        subject=subject,
        template_str=email_template_str,
        context=payload,
    )
    export_file_sent_event(
        export_file_id=payload["export"]["id"], user_id=payload["export"].get("user_id")
    )


@app.task
def send_export_failed_email_task(recipient_email: str, payload: dict, config: dict):
    email_config = EmailConfig(**config)
    email_template_str = get_email_template_or_default(
        constants.PLUGIN_ID,
        constants.CSV_EXPORT_FAILED_TEMPLATE_FIELD,
        constants.CSV_EXPORT_FAILED_TEMPLATE_DEFAULT_TEMPLATE,
    )
    subject = get_email_subject(
        constants.PLUGIN_ID,
        constants.CSV_EXPORT_FAILED_SUBJECT_FIELD,
        constants.CSV_EXPORT_FAILED_DEFAULT_SUBJECT,
    )
    send_email(
        config=email_config,
        recipient_list=[recipient_email],
        subject=subject,
        template_str=email_template_str,
        context=payload,
    )
    export_failed_info_sent_event(
        export_file_id=payload["export"]["id"], user_id=payload["export"].get("user_id")
    )


@app.task
def send_staff_order_confirmation_email_task(
    recipient_list: str, payload: dict, config: dict
):
    email_config = EmailConfig(**config)
    email_template_str = get_email_template_or_default(
        constants.PLUGIN_ID,
        constants.STAFF_ORDER_CONFIRMATION_TEMPLATE_FIELD,
        constants.STAFF_ORDER_CONFIRMATION_DEFAULT_TEMPLATE,
    )
    subject = get_email_subject(
        constants.PLUGIN_ID,
        constants.STAFF_ORDER_CONFIRMATION_SUBJECT_FIELD,
        constants.STAFF_ORDER_CONFIRMATION_DEFAULT_SUBJECT,
    )
    send_email(
        config=email_config,
        recipient_list=recipient_list,
        subject=subject,
        template_str=email_template_str,
        context=payload,
    )
