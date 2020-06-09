import datetime
from unittest.mock import Mock, patch

import pytz
from freezegun import freeze_time

from saleor.core import JobStatus
from saleor.csv import ExportEvents, FileTypes
from saleor.csv.models import ExportEvent
from saleor.csv.tasks import export_products_task, on_task_failure, on_task_success


@patch("saleor.csv.tasks.export_products")
def test_export_products_task(export_products_mock, user_export_file):
    # given
    scope = {"all": ""}
    export_info = {"fields": "name"}
    file_type = FileTypes.CSV
    delimiter = ";"

    # when
    export_products_task(user_export_file.id, scope, export_info, file_type, delimiter)

    # then
    export_products_mock.called_once_with()


@patch("saleor.csv.tasks.send_export_failed_info")
def test_on_task_failure(send_export_failed_info_mock, user_export_file):
    exc = Exception("Test")
    task_id = "task_id"
    args = [user_export_file.pk, {"all": ""}]
    kwargs = {}
    info_type = "Test error"
    info = Mock(type=info_type)

    assert user_export_file.status == JobStatus.PENDING
    assert user_export_file.created_at
    previous_updated_at = user_export_file.updated_at

    with freeze_time(datetime.datetime.now()) as frozen_datetime:
        on_task_failure(None, exc, task_id, args, kwargs, info)

        user_export_file.refresh_from_db()
        assert user_export_file.updated_at == pytz.utc.localize(frozen_datetime())

    assert user_export_file.updated_at != previous_updated_at
    assert user_export_file.status == JobStatus.FAILED
    assert user_export_file.created_at
    assert user_export_file.updated_at != previous_updated_at
    export_failed_event = ExportEvent.objects.get(
        export_file=user_export_file,
        user=user_export_file.user,
        type=ExportEvents.EXPORT_FAILED,
    )
    assert export_failed_event.parameters == {
        "message": str(exc),
        "error_type": info_type,
    }

    send_export_failed_info_mock.called_once_with(user_export_file, "export_failed")


def test_on_task_success(user_export_file):
    task_id = "task_id"
    args = [user_export_file.pk, {"filter": {}}]
    kwargs = {}

    assert user_export_file.status == JobStatus.PENDING
    assert user_export_file.created_at
    previous_updated_at = user_export_file.updated_at

    with freeze_time(datetime.datetime.now()) as frozen_datetime:
        on_task_success(None, None, task_id, args, kwargs)

        user_export_file.refresh_from_db()
        assert user_export_file.updated_at == pytz.utc.localize(frozen_datetime())
        assert user_export_file.updated_at != previous_updated_at

    assert user_export_file.status == JobStatus.SUCCESS
    assert user_export_file.created_at
    assert ExportEvent.objects.filter(
        export_file=user_export_file,
        user=user_export_file.user,
        type=ExportEvents.EXPORT_SUCCESS,
    )
