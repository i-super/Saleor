from collections import OrderedDict
from collections.abc import Iterable

import graphene
from django.core.serializers.json import Serializer as JSONSerializer
from django.core.serializers.python import Serializer as PythonBaseSerializer


class PythonSerializer(PythonBaseSerializer):
    def get_dump_object(self, obj):
        obj_id = graphene.Node.to_global_id(obj._meta.object_name, obj.id)
        data = OrderedDict([("type", str(obj._meta.object_name)), ("id", obj_id)])
        data.update(self._current)
        return data


class WebhookSerializer(JSONSerializer):
    def __init__(self):
        super().__init__()
        self.additional_fields = {}

    def serialize(
        self,
        queryset,
        *,
        stream=None,
        fields=None,
        use_natural_foreign_keys=False,
        use_natural_primary_keys=False,
        progress_output=None,
        object_count=0,
        **options,
    ):
        self.additional_fields = options.pop("additional_fields", {})
        return super().serialize(
            queryset,
            stream=stream,
            fields=fields,
            use_natural_foreign_keys=use_natural_foreign_keys,
            use_natural_primary_keys=use_natural_primary_keys,
            progress_output=progress_output,
            object_count=object_count,
            **options,
        )

    def get_dump_object(self, obj):
        obj_id = graphene.Node.to_global_id(obj._meta.object_name, obj.id)
        data = OrderedDict([("type", str(obj._meta.object_name)), ("id", obj_id)])
        python_serializer = PythonSerializer()
        for field_name, (qs, fields) in self.additional_fields.items():
            data_to_serialize = qs(obj)
            if not data_to_serialize:
                data[field_name] = None
            elif isinstance(data_to_serialize, Iterable):
                data[field_name] = python_serializer.serialize(
                    data_to_serialize, fields=fields
                )
            else:
                data[field_name] = python_serializer.serialize(
                    [data_to_serialize], fields=fields
                )[0]
        data.update(self._current)
        return data
