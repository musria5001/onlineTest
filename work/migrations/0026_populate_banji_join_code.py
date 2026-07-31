# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import random

from django.db import migrations


def make_join_code(used_codes):
    while True:
        code = '%04d' % random.randint(1000, 9999)
        if code not in used_codes:
            used_codes.add(code)
            return code


def populate_join_code(apps, schema_editor):
    BanJi = apps.get_model('work', 'BanJi')
    used_codes = set(
        BanJi.objects.exclude(join_code__isnull=True).exclude(join_code='').values_list('join_code', flat=True)
    )
    for banji in BanJi.objects.filter(join_code__isnull=True):
        banji.join_code = make_join_code(used_codes)
        banji.save(update_fields=['join_code'])
    for banji in BanJi.objects.filter(join_code=''):
        banji.join_code = make_join_code(used_codes)
        banji.save(update_fields=['join_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0025_banji_join_code'),
    ]

    operations = [
        migrations.RunPython(populate_join_code, migrations.RunPython.noop),
    ]
