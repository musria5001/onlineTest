# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0024_auto_20211221_1443'),
    ]

    operations = [
        migrations.AddField(
            model_name='banji',
            name='join_code',
            field=models.CharField(blank=True, max_length=4, null=True, unique=True, verbose_name='班级码'),
        ),
    ]
