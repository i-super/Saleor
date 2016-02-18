# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-02-08 18:28
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0010_auto_20160129_0826'),
    ]

    operations = [
        migrations.CreateModel(
            name='VariantImage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='product.ProductImage')),
                ('variant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='product.ProductVariant')),
            ],
        ),
        migrations.AddField(
            model_name='productvariant',
            name='images',
            field=models.ManyToManyField(through='product.VariantImage', to='product.ProductImage'),
        ),
    ]
