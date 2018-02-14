import pytest

from saleor.order.emails import (
    send_order_confirmation, send_payment_confirmation)


@pytest.mark.django_db
@pytest.mark.integration
@pytest.mark.skip(reason="It causes other tests to fail right now")
def test_email_sending_asynchronously(
        transactional_db, celery_app, celery_worker, order_with_lines):
    order = send_order_confirmation.delay(
        'joe.doe@foo.com', '/nowhere/to/go', order_with_lines.pk)
    payment = send_payment_confirmation.delay('joe.doe@foo.com', '/nowhere/')
    order.get()
    payment.get()
