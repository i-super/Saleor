# Generated by Django 2.2.3 on 2019-07-24 07:56

from django.db import migrations
from django.db.models import Count


def remove_duplicates(apps, schema_editor):
    """Removes any duplicated M2M, and keep only one of them.

    First we select the duplicates, by grouping them and counting them:

        SELECT
            collection_id, product_id, COUNT(*)
        FROM
            public.product_collectionproduct
        GROUP BY
            collection_id, product_id
        HAVING
            COUNT(*) > 1

    Then we retrieve all of them except one (LIMIT = `duplicate_count - 1`).

    Once we have them, we delete each of them manually (cannot directly delete by using
    LIMIT).
    """

    CollectionProduct = apps.get_model("product", "CollectionProduct")

    duplicates = (
        CollectionProduct.objects.values("collection_id", "product_id")
        .annotate(duplicate_count=Count("*"))
        .filter(duplicate_count__gt=1)
    )

    for duplicate in duplicates:
        dup_count = duplicate.pop("duplicate_count")
        delete_limit = dup_count - 1
        entries_to_delete = CollectionProduct.objects.filter(**duplicate)[:delete_limit]
        for entry in entries_to_delete:
            entry.delete()


class Migration(migrations.Migration):

    dependencies = [("product", "0102_attribute_available_in_grid")]

    operations = [
        migrations.RunPython(remove_duplicates),
        migrations.AlterUniqueTogether(
            name="attributeproduct", unique_together={("attribute", "product_type")}
        ),
        migrations.AlterUniqueTogether(
            name="attributevariant", unique_together={("attribute", "product_type")}
        ),
        migrations.AlterUniqueTogether(
            name="collectionproduct", unique_together={("collection", "product")}
        ),
    ]
