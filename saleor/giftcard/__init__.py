class GiftCardExpiryType:
    """The gift card expiry options."""

    NEVER_EXPIRE = "never_expire"
    EXPIRY_PERIOD = "expiry_period"
    EXPIRY_DATE = "expiry_date"

    CHOICES = [
        (NEVER_EXPIRE, "Never expire"),
        (EXPIRY_PERIOD, "Expiry period"),
        (EXPIRY_DATE, "Expiry date"),
    ]


class GiftCardEvents:
    """The different gift card event types."""

    ISSUED = "issued"
    BOUGHT = "bought"
    UPDATED = "updated"
    ACTIVATED = "activated"
    DEACTIVATED = "deactivated"
    BALANCE_RESET = "balance_reset"
    EXPIRY_SETTINGS_UPDATED = "expiry_settings_updated"
    EXPIRY_DATE_SET = "expiry_date_set"
    SENT_TO_CUSTOMER = "sent_to_customer"
    RESENT = "resent"
    NOTE_ADDED = "note_added"
    USED_IN_ORDER = "used_in_order"

    CHOICES = [
        (ISSUED, "The gift card was created be staff user or app."),
        (BOUGHT, "The gift card was bought by customer."),
        (UPDATED, "The gift card was updated."),
        (ACTIVATED, "The gift card was activated."),
        (DEACTIVATED, "The gift card was deactivated."),
        (BALANCE_RESET, "The gift card balance was reset."),
        (EXPIRY_SETTINGS_UPDATED, "The gift card expiry settings was updated."),
        (EXPIRY_DATE_SET, "The expiry date was set."),
        (SENT_TO_CUSTOMER, "The gift card was sent to the customer."),
        (RESENT, "The gift card was resent to the customer."),
        (NOTE_ADDED, "A note was added to the gift card."),
        (USED_IN_ORDER, "The gift card was used in order."),
    ]
