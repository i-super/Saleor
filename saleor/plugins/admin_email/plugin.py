import logging
from dataclasses import dataclass

from ...core.notify_events import AdminNotifyEvent, NotifyEventType
from ..base_plugin import BasePlugin
from . import emails

logger = logging.getLogger(__name__)


@dataclass
class UserEmailConfig:
    account_confirmation_template: str
    account_password_reset_template: str


event_map = {
    AdminNotifyEvent.STAFF_ORDER_CONFIRMATION: emails.send_staff_order_confirmation,
    AdminNotifyEvent.ACCOUNT_SET_STAFF_PASSWORD: emails.send_set_staff_password_email,
    AdminNotifyEvent.CSV_PRODUCT_EXPORT_SUCCESS: emails.send_csv_product_export_success,
    AdminNotifyEvent.CSV_EXPORT_FAILED: emails.send_csv_export_failed,
}


class AdminEmailPlugin(BasePlugin):
    PLUGIN_ID = "mirumee.notifications.admin_email"
    PLUGIN_NAME = "Admin emails"

    # TODO the configuration will be implemented in separate pull request

    # DEFAULT_CONFIGURATION = [
    #     {"name": "account-confirmation_template", "value": None},
    #     {"name": "account-password-reset-template", "value": None},
    # ]
    #
    # CONFIG_STRUCTURE = {
    #     "account-confirmation_template": {
    #         "type": ConfigurationTypeField.SECRET,
    #         "help_text": "",
    #         "label": "Account confirmation template",
    #     },
    #     "account-password-reset-template": {
    #         "type": ConfigurationTypeField.SECRET,
    #         "help_text": "",
    #         "label": "Account password reset template",
    #     },
    # }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # configuration = {item["name"]: item["value"] for item in self.configuration}
        self.active = True

    def notify(self, event: NotifyEventType, payload: dict, previous_value):
        if not self.active:
            return previous_value
        if event not in AdminNotifyEvent.CHOICES:
            return previous_value
        if event not in event_map:
            logger.warning(f"Missing handler for event {event}")
            return previous_value
        event_map[event](payload)  # type: ignore
