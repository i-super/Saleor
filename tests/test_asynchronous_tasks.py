import pytest

from saleor.order.emails import (
    send_order_confirmation, send_payment_confirmation)


@pytest.mark.django_db
@pytest.mark.integration
def test_email_sending_asynchronously(
        transactional_db, celery_app, celery_worker):
    order = send_order_confirmation.delay('joe.doe@foo.com', '/nowhere/to/go')
    payment = send_payment_confirmation.delay('joe.doe@foo.com', '/nowhere/')
    order.get()
    payment.get()
