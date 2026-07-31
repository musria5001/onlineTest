# coding: utf-8
from __future__ import unicode_literals

import io
import os
import random

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from auth_system.models import MyUser
from judge.models import ClassName, KnowledgePoint1, KnowledgePoint2, ChoiceProblem, DuchengProblem
from quiz.models import AnswerRecord
from work.models import BanJi


TEACHER_GROUP = u'\u8001\u5e08'
STUDENT_GROUP = u'\u5b66\u751f'
ADMIN_GROUP = u'\u7ba1\u7406\u5458'

COURSE_NAME = u'\u6f14\u793a\u6d4b\u8bd5\u8bfe\u7a0b'
CLASS_SUFFIX = u'\u73ed'
QUESTION_PREFIX = '[DemoOnlineTest]'

ADMIN_PASSWORD = os.environ.get('ONLINETEST_DEMO_ADMIN_PASSWORD', 'ChangeMeAdmin123!')
TEACHER_PASSWORD = os.environ.get('ONLINETEST_DEMO_TEACHER_PASSWORD', 'ChangeMeTeacher123!')
STUDENT_PASSWORD = os.environ.get('ONLINETEST_DEMO_STUDENT_PASSWORD', 'ChangeMeStudent123!')


def first_or_create(model, defaults=None, **lookup):
    defaults = defaults or {}
    obj = model.objects.filter(**lookup).first()
    if obj:
        changed = False
        for key, value in defaults.items():
            if getattr(obj, key) != value:
                setattr(obj, key, value)
                changed = True
        if changed:
            obj.save()
        return obj, False
    params = {}
    params.update(lookup)
    params.update(defaults)
    return model.objects.create(**params), True


def ensure_user(info, groups):
    user = MyUser.objects.filter(id_num=info['id_num']).first()
    if not user:
        user = MyUser(id_num=info['id_num'])
    user.email = info['email']
    user.username = info['username']
    user.school = u'\u6f14\u793a\u5b66\u6821'
    user.school_short = 'DEMO'
    user.allow_num = info.get('allow_num', 0)
    user.create_num = info.get('create_num', 0)
    user.is_active = True
    user.is_admin = info.get('is_admin', False)
    user.is_superuser = info.get('is_superuser', False)
    user.set_password(info['password'])
    user.save()
    user.groups.clear()
    for group in groups:
        user.groups.add(group)
    return user


def wrong_choice(right_answer):
    options = ['a', 'b', 'c', 'd']
    index = options.index(right_answer)
    return options[(index + 1) % len(options)]


def random_join_code(used_codes):
    while True:
        code = '%04d' % random.randint(1000, 9999)
        if code not in used_codes:
            used_codes.add(code)
            return code


class Command(BaseCommand):
    help = 'Seed demo admin, teachers, classes, students, questions, and answer records.'

    def handle(self, *args, **options):
        with transaction.atomic():
            result = self.seed()
        self.stdout.write('Demo data is ready.')
        self.stdout.write('Accounts report: %s' % result['report_path'])
        for class_info in result['classes']:
            self.stdout.write('%s code: %s' % (class_info['name'], class_info['code']))
        self.stdout.write('Questions: %s, answer records: %s' % (result['question_count'], result['record_count']))

    def seed(self):
        teacher_group, _ = Group.objects.get_or_create(name=TEACHER_GROUP)
        student_group, _ = Group.objects.get_or_create(name=STUDENT_GROUP)
        admin_group, _ = Group.objects.get_or_create(name=ADMIN_GROUP)

        admin_codenames = [
            'add_classname', 'change_classname', 'delete_classname',
            'add_knowledgepoint1', 'change_knowledgepoint1', 'delete_knowledgepoint1',
            'add_knowledgepoint2', 'change_knowledgepoint2', 'delete_knowledgepoint2',
            'add_choiceproblem', 'change_choiceproblem', 'delete_choiceproblem',
            'add_duchengproblem', 'change_duchengproblem', 'delete_duchengproblem',
            'add_problem', 'change_problem', 'delete_problem',
        ]
        teacher_codenames = [
            'add_banji', 'change_banji', 'delete_banji',
        ]
        admin_permissions = Permission.objects.filter(
            content_type__app_label='judge',
            codename__in=admin_codenames
        )
        teacher_permissions = Permission.objects.filter(
            content_type__app_label='work',
            codename__in=teacher_codenames
        )
        admin_group.permissions.clear()
        teacher_group.permissions.clear()
        teacher_group.permissions.add(*teacher_permissions)
        admin_group.permissions.add(*admin_permissions)

        admin_info = {
            'role': 'admin',
            'class_label': '',
            'id_num': 'admin01',
            'email': 'admin01@test.cn',
            'username': u'\u6f14\u793a\u7ba1\u7406\u5458',
            'password': ADMIN_PASSWORD,
            'is_admin': False,
            'is_superuser': False,
            'allow_num': 200,
            'create_num': 200,
        }
        teacher_infos = [
            {
                'role': 'teacher',
                'class_label': 'A,B',
                'id_num': 'teacher01',
                'email': 'teacher01@test.cn',
                'username': u'AB\u73ed\u6559\u5e08',
                'password': TEACHER_PASSWORD,
                'allow_num': 100,
                'create_num': 100,
            },
            {
                'role': 'teacher',
                'class_label': 'C,D',
                'id_num': 'teacher02',
                'email': 'teacher02@test.cn',
                'username': u'CD\u73ed\u6559\u5e08',
                'password': TEACHER_PASSWORD,
                'allow_num': 100,
                'create_num': 100,
            },
        ]

        student_infos = []
        for class_label in ['A', 'B', 'C', 'D']:
            for number in range(1, 11):
                student_infos.append({
                    'role': 'student',
                    'class_label': class_label,
                    'id_num': 'stu%s%02d' % (class_label, number),
                    'email': 'stu%s%02d@test.cn' % (class_label.lower(), number),
                    'username': u'%s%s\u5b66\u751f%02d' % (class_label, CLASS_SUFFIX, number),
                    'password': STUDENT_PASSWORD,
                })

        demo_ids = [admin_info['id_num']] + [i['id_num'] for i in teacher_infos] + [i['id_num'] for i in student_infos]
        demo_class_names = [u'%s%s' % (label, CLASS_SUFFIX) for label in ['A', 'B', 'C', 'D']]

        AnswerRecord.objects.filter(user__id_num__in=demo_ids).delete()
        AnswerRecord.objects.filter(banji__name__in=demo_class_names).delete()
        ChoiceProblem.objects.filter(title__startswith=QUESTION_PREFIX).delete()
        DuchengProblem.objects.filter(title__startswith=QUESTION_PREFIX).delete()

        admin = ensure_user(admin_info, [admin_group])
        teachers = [
            ensure_user(teacher_infos[0], [teacher_group]),
            ensure_user(teacher_infos[1], [teacher_group]),
        ]
        students_by_class = {'A': [], 'B': [], 'C': [], 'D': []}
        for info in student_infos:
            students_by_class[info['class_label']].append(ensure_user(info, [student_group]))

        course, _ = first_or_create(ClassName, name=COURSE_NAME)
        kp1_data = [
            (u'\u7b2c1\u7ae0 \u57fa\u7840\u7ec3\u4e60', [
                u'1.1 \u987a\u5e8f\u7ed3\u6784',
                u'1.2 \u6761\u4ef6\u5224\u65ad',
            ]),
            (u'\u7b2c2\u7ae0 \u8fdb\u9636\u7ec3\u4e60', [
                u'2.1 \u5faa\u73af\u7ed3\u6784',
                u'2.2 \u51fd\u6570\u5165\u95e8',
            ]),
        ]

        kp2s = []
        for kp1_name, kp2_names in kp1_data:
            kp1, _ = first_or_create(KnowledgePoint1, name=kp1_name, defaults={'classname': course})
            if kp1.classname_id != course.id:
                kp1.classname = course
                kp1.save()
            for kp2_name in kp2_names:
                kp2, _ = first_or_create(KnowledgePoint2, name=kp2_name, defaults={'upperPoint': kp1})
                if kp2.upperPoint_id != kp1.id:
                    kp2.upperPoint = kp1
                    kp2.save()
                kp2s.append(kp2)

        question_templates = [
            (
                u'下面哪个是合法的 Python 变量名？',
                '1name', 'student_name', 'student-name', 'class', 'b'
            ),
            (
                u'表达式 1 + 2 * 3 的结果是多少？',
                '7', '9', '6', '5', 'a'
            ),
            (
                u'Python 中用于开始条件判断的关键字是哪个？',
                'for', 'if', 'def', 'print', 'b'
            ),
            (
                u'当循环次数已知时，通常使用哪种循环？',
                'for', 'if', 'try', 'import', 'a'
            ),
            (
                u'函数中用于返回结果的语句是哪一个？',
                'break', 'return', 'continue', 'pass', 'b'
            ),
        ]

        questions_by_kp2 = {}
        for kp2 in kp2s:
            questions_by_kp2[kp2.id] = []
            for index, data in enumerate(question_templates, 1):
                title, a, b, c, d, right_answer = data
                question = ChoiceProblem.objects.create(
                    title=u'%s %s 第%02d题：%s' % (QUESTION_PREFIX, kp2.name, index, title),
                    a=a,
                    b=b,
                    c=c,
                    d=d,
                    right_answer=right_answer,
                    creater=admin,
                )
                question.classname.add(course)
                question.knowledgePoint1.add(kp2.upperPoint)
                question.knowledgePoint2.add(kp2)
                questions_by_kp2[kp2.id].append(question)

        now = timezone.now()
        start_time = now - timezone.timedelta(days=1)
        end_time = now + timezone.timedelta(days=365)
        class_assignments = [
            ('A', teachers[0]),
            ('B', teachers[0]),
            ('C', teachers[1]),
            ('D', teachers[1]),
        ]
        banjis = {}
        used_join_codes = set(
            BanJi.objects.exclude(name__in=demo_class_names).exclude(join_code__isnull=True).values_list('join_code', flat=True)
        )
        for class_label, teacher in class_assignments:
            name = u'%s%s' % (class_label, CLASS_SUFFIX)
            banji, _ = first_or_create(
                BanJi,
                name=name,
                defaults={
                    'teacher': teacher,
                    'courser': course,
                    'start_time': start_time,
                    'end_time': end_time,
                    'score_weight': '{"pscore":1,"mscore":0,"sign":0}',
                }
            )
            banji.teacher = teacher
            banji.courser = course
            banji.start_time = start_time
            banji.end_time = end_time
            banji.score_weight = '{"pscore":1,"mscore":0,"sign":0}'
            banji.join_code = random_join_code(used_join_codes)
            banji.save()
            banji.students.clear()
            for student in students_by_class[class_label]:
                banji.students.add(student)
            banjis[class_label] = banji

        record_count = 0
        for class_index, class_label in enumerate(['A', 'B', 'C', 'D']):
            banji = banjis[class_label]
            for student_index, student in enumerate(students_by_class[class_label], 1):
                for kp2_index, kp2 in enumerate(kp2s, 1):
                    for round_num in range(1, 4):
                        for question_index, question in enumerate(questions_by_kp2[kp2.id], 1):
                            marker = class_index * 100 + student_index * 7 + kp2_index * 5 + round_num * 3 + question_index
                            if marker % 6 == 0:
                                is_correct = False
                                points = 0
                                student_answer = wrong_choice(question.right_answer)
                            elif marker % 5 == 0:
                                is_correct = True
                                points = 0.5
                                student_answer = question.right_answer
                            else:
                                is_correct = True
                                points = 1
                                student_answer = question.right_answer
                            AnswerRecord.objects.create(
                                user=student,
                                question_type=AnswerRecord.CHOICE,
                                choice_question=question,
                                kp2=kp2,
                                banji=banji,
                                is_correct=is_correct,
                                points=points,
                                round_num=round_num,
                                student_answer=student_answer,
                            )
                            record_count += 1

        account_rows = [admin_info] + teacher_infos + student_infos
        class_rows = []
        for class_label in ['A', 'B', 'C', 'D']:
            teacher = banjis[class_label].teacher
            class_rows.append({
                'name': banjis[class_label].name,
                'code': banjis[class_label].join_code,
                'teacher': teacher.id_num,
                'course': course.name,
            })

        report_path = os.path.join(settings.BASE_DIR, 'demo_accounts.md')
        self.write_report(report_path, account_rows, class_rows, len(kp2s) * len(question_templates), record_count)

        return {
            'report_path': report_path,
            'classes': class_rows,
            'question_count': len(kp2s) * len(question_templates),
            'record_count': record_count,
        }

    def write_report(self, report_path, accounts, classes, question_count, record_count):
        lines = [
            '# onlineTest 演示账号',
            '',
            '登录页：http://127.0.0.1:8000/',
            '管理员内容页：http://127.0.0.1:8000/work/courser-list/',
            '',
            '管理员创建题目数：%s' % question_count,
            '学生答题记录数：%s' % record_count,
            '',
            '## 班级',
            '',
            '| 班级 | 班级码 | 教师账号 | 课程 |',
            '| --- | --- | --- | --- |',
        ]
        for item in classes:
            lines.append('| %s | %s | %s | %s |' % (item['name'], item['code'], item['teacher'], item['course']))

        lines.extend([
            '',
            '## 账号',
            '',
            '| 角色 | 班级 | 姓名 | 登录账号 | 邮箱 | 密码 |',
            '| --- | --- | --- | --- | --- | --- |',
        ])
        for item in accounts:
            lines.append('| %s | %s | %s | %s | %s | %s |' % (
                item['role'],
                item['class_label'],
                item['username'],
                item['id_num'],
                item['email'],
                item['password'],
            ))

        with io.open(report_path, 'w', encoding='utf-8-sig') as output:
            output.write('\n'.join(lines))
            output.write('\n')
