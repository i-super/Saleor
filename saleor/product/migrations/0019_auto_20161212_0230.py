# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-12-12 08:30
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("product", "0018_auto_20161207_0844")]

    operations = [
        migrations.CreateModel(
            name="ProductClass",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=128, verbose_name="name")),
                ("has_variants", models.BooleanField(default=True)),
                (
                    "product_attributes",
                    models.ManyToManyField(
                        blank=True,
                        related_name="products_class",
                        to="product.ProductAttribute",
                    ),
                ),
                (
                    "variant_attributes",
                    models.ManyToManyField(
                        blank=True,
                        related_name="product_variants_class",
                        to="product.ProductAttribute",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="product",
            name="product_class",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="products",
                to="product.ProductClass",
            ),
        ),
    ]
