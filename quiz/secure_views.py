from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db.models import Sum

from auth_system.models import MyUser
from judge.models import ClassName, KnowledgePoint1, KnowledgePoint2, ChoiceProblem, DuchengProblem
from work.models import BanJi
from .models import AnswerRecord


def _student_banjis(user):
    return BanJi.objects.filter(students=user).select_related('teacher', 'courser')


def _student_courses(user):
    course_ids = _student_banjis(user).values_list('courser_id', flat=True).distinct()
    return ClassName.objects.filter(id__in=course_ids).prefetch_related('knowledgepoint1_set__knowledgepoint2_set')


def _kp2_total_questions(kp2):
    return ChoiceProblem.objects.filter(knowledgePoint2=kp2).count() + DuchengProblem.objects.filter(knowledgePoint2=kp2).count()


def _kp2_completed_rounds(user, kp2):
    total_qs = _kp2_total_questions(kp2)
    if total_qs <= 0:
        return 0
    q_per_round = {}
    for record in AnswerRecord.objects.filter(user=user, kp2=kp2):
        qid = record.choice_question_id if record.question_type == 'choice' else record.ducheng_question_id
        q_per_round.setdefault(record.round_num, set()).add(qid)
    return sum(1 for qs in q_per_round.values() if len(qs) >= total_qs)


def _course_accessible(user, course):
    return _student_banjis(user).filter(courser=course).exists()


def _kp2_accessible(user, kp2):
    if not kp2.upperPoint:
        return False
    if not _course_accessible(user, kp2.upperPoint.classname):
        return False
    prev_complete = True
    for item in kp2.upperPoint.knowledgepoint2_set.all().order_by('id'):
        total = _kp2_total_questions(item)
        if item.pk == kp2.pk:
            return total <= 0 or prev_complete
        if total > 0:
            prev_complete = prev_complete and (_kp2_completed_rounds(user, item) >= 3)
    return False


def _first_banji_for_course(user, course):
    return _student_banjis(user).filter(courser=course).first()


def _student_group():
    return Group.objects.filter(name__in=['瀛︾敓', 'student']).first()


@login_required
def kp_tree(request):
    if request.user.is_content_admin:
        return redirect('list_coursers')
    if request.user.isTeacher():
        return redirect('quiz_teacher_dashboard')

    if not _student_banjis(request.user).exists():
        return render(request, 'quiz/join_banji.html', {
            'title': '加入班级',
            'position': 'quiz_join_banji',
            'banjis': [],
            'message': '',
            'error': '',
        })

    course_data = []
    for course in _student_courses(request.user):
        kp1_list = []
        course_prev_complete = True
        for idx, kp1 in enumerate(course.knowledgepoint1_set.all()):
            kp2_list = []
            kp1_correct = 0
            kp1_answered = 0
            kp1_total = 0
            prev_complete = course_prev_complete
            for kp2 in kp1.knowledgepoint2_set.all():
                total = _kp2_total_questions(kp2)
                all_recs = AnswerRecord.objects.filter(user=request.user, kp2=kp2)
                total_points = all_recs.aggregate(s=Sum('points'))['s'] or 0
                completed_rounds = _kp2_completed_rounds(request.user, kp2)
                kp1_correct += int(total_points)
                kp1_answered += all_recs.count()
                kp1_total += total
                kp2_list.append({
                    'id': kp2.id,
                    'name': kp2.name,
                    'total': total,
                    'answered': all_recs.count(),
                    'correct': int(total_points),
                    'completed_rounds': completed_rounds,
                    'max_rounds': 3,
                    'complete': completed_rounds >= 3,
                    'locked': not prev_complete and total > 0,
                })
                if total > 0:
                    prev_complete = prev_complete and (completed_rounds >= 3)
            course_prev_complete = prev_complete
            if kp2_list:
                kp1_list.append({
                    'id': kp1.id, 'name': kp1.name, 'kp2s': kp2_list,
                    'index': idx + 1,
                    'total_correct': kp1_correct,
                    'total_answered': kp1_answered,
                    'total_qs': kp1_total,
                    'show_ellipsis': False,
                })
        if len(kp1_list) > 3:
            for i, kp1_item in enumerate(kp1_list):
                kp1_item['hidden'] = (i >= 3)
            kp1_list[2]['show_ellipsis'] = True
            kp1_list[2]['remaining'] = len(kp1_list) - 3
        if kp1_list:
            course_data.append({'id': course.id, 'name': course.name, 'kp1s': kp1_list})

    return render(request, 'quiz/kp_tree.html', {
        'title': '知识点练习',
        'position': 'quiz_kp_tree',
        'course_data': course_data,
        'need_join_class': False,
        'total_points': AnswerRecord.objects.filter(user=request.user, is_correct=True).count(),
    })


@login_required
def join_banji(request):
    if request.user.isTeacher() or request.user.is_content_admin:
        raise Http404()

    message = ''
    error = ''
    if request.method == 'POST':
        code = request.POST.get('banji_code', '').strip()
        if not (code.isdigit() and len(code) == 4):
            error = '班级码必须是 4 位数字'
        else:
            banji = BanJi.objects.filter(join_code=code).select_related('teacher', 'courser').first()
            if not banji:
                error = '未找到该班级'
            elif banji.students.filter(pk=request.user.pk).exists():
                message = '你已经加入该班级'
            else:
                banji.students.add(request.user)
                message = '加入班级成功'

    return render(request, 'quiz/join_banji.html', {
            'title': '加入班级',
        'position': 'quiz_join_banji',
        'banjis': _student_banjis(request.user),
        'message': message,
        'error': error,
    })


@login_required
def answer_question(request, kp2_id):
    if request.user.isTeacher() or request.user.is_content_admin:
        raise Http404()
    kp2 = get_object_or_404(KnowledgePoint2, pk=kp2_id)
    if not _kp2_accessible(request.user, kp2):
        raise Http404()

    all_records = AnswerRecord.objects.filter(user=request.user, kp2=kp2)
    total_qs = _kp2_total_questions(kp2)
    if total_qs == 0:
        return render(request, 'quiz/kp2_complete.html', {
            'title': '知识点练习',
            'kp2': kp2,
            'correct': 0, 'total': 0, 'round': 0, 'max_rounds': 3,
            'next_url': None,
        })

    q_per_round = {}
    for r in all_records:
        qid = r.choice_question_id if r.question_type == 'choice' else r.ducheng_question_id
        q_per_round.setdefault(r.round_num, set()).add(qid)

    show_done = request.GET.get('done')
    work_round = 1
    for rnd in range(1, 4):
        if len(q_per_round.get(rnd, set())) < total_qs:
            work_round = rnd
            break
    else:
        total_points = all_records.aggregate(s=Sum('points'))['s'] or 0
        return render(request, 'quiz/kp2_complete.html', {
            'title': '知识点练习',
            'kp2': kp2,
            'correct': int(total_points), 'total': 3, 'round': 3, 'max_rounds': 3,
            'next_url': None,
        })

    if show_done:
        return render(request, 'quiz/kp2_round_done.html', {
            'title': '知识点练习',
            'kp2': kp2,
            'round': int(show_done), 'max_rounds': 3,
            'remaining': 3 - int(show_done),
            'next_url': 'quiz_answer',
        })

    cur_answered = len(q_per_round.get(work_round, set()))
    cur_correct = q_per_round.get(work_round, set())
    choice_available = [q for q in ChoiceProblem.objects.filter(knowledgePoint2__id=kp2_id).order_by('id') if q.id not in cur_correct]
    ducheng_available = [q for q in DuchengProblem.objects.filter(knowledgePoint2__id=kp2_id).order_by('ducheng_id') if q.ducheng_id not in cur_correct]
    merged = []
    for qt, pl in (('choice', choice_available), ('ducheng', ducheng_available)):
        for q in pl:
            merged.append((qt, q))
    if not merged:
        total_points = all_records.aggregate(s=Sum('points'))['s'] or 0
        return render(request, 'quiz/kp2_complete.html', {
            'title': '知识点练习',
            'kp2': kp2,
            'correct': int(total_points), 'total': 3, 'round': work_round, 'max_rounds': 3,
            'next_url': None,
        })
    choices = [(t, q) for t, q in merged if t == 'choice']
    ducheng = [(t, q) for t, q in merged if t == 'ducheng']
    merged = []
    max_len = max(len(choices), len(ducheng))
    for i in range(max_len):
        if i < len(choices):
            merged.append(choices[i])
        if i < len(ducheng):
            merged.append(ducheng[i])
    qtype, question = merged[0]

    context = {
        'title': kp2.name,
        'position': 'quiz_kp_tree',
        'kp2': kp2,
        'question': question,
        'progress': {'round': work_round, 'max_rounds': 3, 'cur_answered': cur_answered, 'total': total_qs},
    }
    if qtype == 'ducheng':
        return render(request, 'quiz/answer_ducheng.html', context)
    return render(request, 'quiz/answer.html', context)


@login_required
def submit_answer(request, kp2_id):
    if request.user.isTeacher() or request.user.is_content_admin:
        raise Http404()
    kp2 = get_object_or_404(KnowledgePoint2, pk=kp2_id)
    if not _kp2_accessible(request.user, kp2):
        raise Http404()

    qtype = request.POST.get('question_type', 'choice')
    if qtype == 'choice':
        question_id = request.POST.get('question_id')
        selected = request.POST.get('selected', '').strip().lower()
        if not question_id or selected not in ('a', 'b', 'c', 'd'):
            return JsonResponse({'error': 'Invalid parameters'}, status=400)
        question = get_object_or_404(ChoiceProblem, pk=question_id)
        if not question.knowledgePoint2.filter(pk=kp2_id).exists():
            return JsonResponse({'error': 'Question does not belong to this knowledge point'}, status=400)
        is_correct = (selected == question.right_answer)
        total_qs = _kp2_total_questions(kp2)
        all_records = AnswerRecord.objects.filter(user=request.user, kp2=kp2)
        q_per_round = {}
        for r in all_records:
            qid = r.choice_question_id if r.question_type == 'choice' else r.ducheng_question_id
            q_per_round.setdefault(r.round_num, set()).add(qid)
        work_round = max(q_per_round.keys()) if q_per_round else 1
        if len(q_per_round.get(work_round, set())) >= total_qs:
            work_round += 1
        points = 1 if is_correct else 0
        banji = _first_banji_for_course(request.user, kp2.upperPoint.classname)
        AnswerRecord.objects.create(
            user=request.user, question_type='choice', choice_question=question, kp2=kp2, banji=banji,
            is_correct=is_correct, points=points, round_num=work_round, student_answer=selected,
        )
        cnt_choice = AnswerRecord.objects.filter(user=request.user, kp2=kp2, round_num=work_round, question_type='choice').values('choice_question_id').distinct().count()
        cnt_ducheng = AnswerRecord.objects.filter(user=request.user, kp2=kp2, round_num=work_round, question_type='ducheng').values('ducheng_question_id').distinct().count()
        done_rnd = work_round if (cnt_choice + cnt_ducheng) >= total_qs else None
        return JsonResponse({'correct': is_correct, 'qtype': 'choice', 'right_answer': question.right_answer, 'selected': selected, 'done': done_rnd})

    question_id = request.POST.get('question_id')
    student_answer = request.POST.get('selected', '').strip()
    if not question_id or not student_answer:
        return JsonResponse({'error': 'Answer required'}, status=400)
    question = get_object_or_404(DuchengProblem, pk=question_id)
    if not question.knowledgePoint2.filter(pk=kp2_id).exists():
        return JsonResponse({'error': 'Question does not belong to this knowledge point'}, status=400)
    correct_answers = [a.strip() for a in question.answer.split('|||') if a.strip()]
    is_correct = student_answer in correct_answers
    total_qs = _kp2_total_questions(kp2)
    all_records = AnswerRecord.objects.filter(user=request.user, kp2=kp2)
    q_per_round = {}
    for r in all_records:
        qid = r.choice_question_id if r.question_type == 'choice' else r.ducheng_question_id
        q_per_round.setdefault(r.round_num, set()).add(qid)
    work_round = max(q_per_round.keys()) if q_per_round else 1
    if len(q_per_round.get(work_round, set())) >= total_qs:
        work_round += 1
    points = 1 if is_correct else 0
    banji = _first_banji_for_course(request.user, kp2.upperPoint.classname)
    AnswerRecord.objects.create(
        user=request.user, question_type='ducheng', ducheng_question=question, kp2=kp2, banji=banji,
        is_correct=is_correct, points=points, round_num=work_round, student_answer=student_answer,
    )
    cnt_choice = AnswerRecord.objects.filter(user=request.user, kp2=kp2, round_num=work_round, question_type='choice').values('choice_question_id').distinct().count()
    cnt_ducheng = AnswerRecord.objects.filter(user=request.user, kp2=kp2, round_num=work_round, question_type='ducheng').values('ducheng_question_id').distinct().count()
    done_rnd = work_round if (cnt_choice + cnt_ducheng) >= total_qs else None
    return JsonResponse({'correct': is_correct, 'qtype': 'ducheng', 'right_answer': question.answer, 'selected': student_answer, 'done': done_rnd})


@login_required
def my_points(request):
    if request.user.isTeacher() or request.user.is_content_admin:
        raise Http404()
    all_my = AnswerRecord.objects.filter(user=request.user)
    total_correct = all_my.filter(is_correct=True).count()
    total_answered = all_my.count()
    total_points = int(all_my.aggregate(s=Sum('points'))['s'] or 0)
    accuracy = round(total_correct * 100 / total_answered, 1) if total_answered > 0 else 0
    kp2_data = []
    all_kp2s = KnowledgePoint2.objects.filter(answerrecord__user=request.user).distinct()
    for kp2 in all_kp2s:
        correct = AnswerRecord.objects.filter(user=request.user, kp2=kp2, is_correct=True).count()
        total = AnswerRecord.objects.filter(user=request.user, kp2=kp2).count()
        kp2_data.append({'name': kp2.name, 'kp1_name': kp2.upperPoint.name if kp2.upperPoint else '', 'correct': correct, 'total': total})
    return render(request, 'quiz/my_points.html', {'title': '我的积分', 'position': 'quiz_points', 'total_points': total_points, 'total_answered': total_answered, 'total_correct': total_correct, 'accuracy': accuracy, 'kp2_data': kp2_data})


@login_required
def leaderboard(request):
    if request.user.isTeacher() or request.user.is_content_admin:
        raise Http404()
    my_banjis = _student_banjis(request.user)
    banji_rankings = []
    student_group = _student_group()
    for banji in my_banjis:
        if student_group:
            student_ids = banji.students.filter(groups=student_group).values_list('id', flat=True)
        else:
            student_ids = banji.students.values_list('id', flat=True)
        rankings = AnswerRecord.objects.filter(user__in=student_ids).values('user__username', 'user__id_num', 'user_id').annotate(points=Sum('points')).order_by('-points')
        my_rank = None
        my_points_val = None
        for idx, row in enumerate(rankings):
            row['rank'] = idx + 1
            if row['user_id'] == request.user.id:
                my_rank = idx + 1
                my_points_val = row['points']
        banji_rankings.append({'banji_name': banji.name, 'rankings': rankings[:50], 'my_rank': my_rank, 'my_points': my_points_val, 'total_students': rankings.count()})
    return render(request, 'quiz/leaderboard.html', {'title': '积分排行榜', 'position': 'quiz_leaderboard', 'banji_rankings': banji_rankings})


@login_required
def teacher_dashboard(request):
    if request.user.is_content_admin or not request.user.isTeacher():
        raise Http404()
    student_group = _student_group()
    banjis = BanJi.objects.filter(teacher=request.user)
    banji_data = []
    for bj in banjis:
        if student_group:
            student_ids = bj.students.filter(groups=student_group).values_list('id', flat=True)
        else:
            student_ids = bj.students.values_list('id', flat=True)
        student_count = len(student_ids)
        total_answered = AnswerRecord.objects.filter(banji=bj, user__in=student_ids).count()
        total_correct = AnswerRecord.objects.filter(banji=bj, user__in=student_ids, is_correct=True).count()
        active_count = AnswerRecord.objects.filter(banji=bj, user__in=student_ids).values('user').distinct().count()
        banji_data.append({'id': bj.id, 'name': bj.name, 'student_count': student_count, 'active_count': active_count, 'total_answered': total_answered, 'total_correct': total_correct, 'correct_rate': round(total_correct * 100 / total_answered, 1) if total_answered > 0 else 0, 'code': bj.join_code or bj.id})
    return render(request, 'quiz/teacher_dashboard.html', {'title': '答题统计', 'position': 'quiz_teacher_dashboard', 'banji_data': banji_data})


@login_required
def teacher_class_progress(request, banji_id):
    if request.user.is_content_admin or not request.user.isTeacher():
        raise Http404()
    banji = get_object_or_404(BanJi, pk=banji_id)
    if banji.teacher != request.user and not request.user.is_superuser:
        raise Http404()
    students = banji.students.all()
    student_data = []
    for stu in students:
        total_correct = AnswerRecord.objects.filter(user=stu, banji=banji, is_correct=True).count()
        total_answered = AnswerRecord.objects.filter(user=stu, banji=banji).count()
        student_data.append({'id': stu.id, 'username': stu.username, 'id_num': stu.id_num, 'total_correct': total_correct, 'total_answered': total_answered})
    student_data.sort(key=lambda x: x['total_correct'], reverse=True)
    return render(request, 'quiz/teacher_class_progress.html', {'title': '%s - 学生答题情况' % banji.name, 'position': 'quiz_teacher_dashboard', 'banji': banji, 'student_data': student_data, 'kp2_count': KnowledgePoint2.objects.count()})


@login_required
def teacher_student_records(request, banji_id, user_id):
    if request.user.is_content_admin or not request.user.isTeacher():
        raise Http404()
    banji = get_object_or_404(BanJi, pk=banji_id)
    if banji.teacher != request.user and not request.user.is_superuser:
        raise Http404()
    stu = get_object_or_404(MyUser, pk=user_id)
    records = AnswerRecord.objects.filter(user=stu, banji=banji).select_related('choice_question', 'ducheng_question', 'kp2', 'kp2__upperPoint').order_by('-created_time')[:200]
    wrong_records = AnswerRecord.objects.filter(user=stu, banji=banji, is_correct=False).select_related('choice_question', 'ducheng_question', 'kp2', 'kp2__upperPoint').order_by('-created_time')[:200]
    kp2_summary = []
    kp2_ids = AnswerRecord.objects.filter(user=stu, banji=banji).values_list('kp2', flat=True).distinct()
    base_qs = AnswerRecord.objects.filter(user=stu, banji=banji)
    for kp2_id in kp2_ids:
        kp2 = KnowledgePoint2.objects.get(pk=kp2_id)
        correct = base_qs.filter(kp2=kp2, is_correct=True).count()
        total = base_qs.filter(kp2=kp2).count()
        kp2_summary.append({'name': kp2.name, 'kp1_name': kp2.upperPoint.name if kp2.upperPoint else '', 'correct': correct, 'total': total})
    tc = base_qs.filter(is_correct=True).count()
    tn = base_qs.count()
    return render(request, 'quiz/teacher_student_records.html', {'title': '%s - 答题记录' % stu.username, 'position': 'quiz_teacher_dashboard', 'banji': banji, 'stu': stu, 'records': records, 'wrong_records': wrong_records, 'kp2_summary': kp2_summary, 'total_correct': tc, 'total_count': tn, 'total_wrong': tn - tc})


@login_required
def teacher_kp_manage(request):
    if request.user.is_content_admin or not request.user.isTeacher():
        raise Http404()
    kp2s = KnowledgePoint2.objects.all().select_related('upperPoint__classname')
    kp2_data = []
    for kp2 in kp2s:
        total = ChoiceProblem.objects.filter(knowledgePoint2=kp2).count()
        kp2_data.append({'id': kp2.id, 'name': kp2.name, 'kp1_name': kp2.upperPoint.name if kp2.upperPoint else '', 'course_name': kp2.upperPoint.classname.name if kp2.upperPoint else '', 'total': total})
    return render(request, 'quiz/teacher_kp_manage.html', {'title': '知识点管理', 'position': 'quiz_teacher_kp_manage', 'kp2_data': kp2_data})


@login_required
def teacher_kp_questions(request, kp2_id):
    if request.user.is_content_admin or not request.user.isTeacher():
        raise Http404()
    kp2 = get_object_or_404(KnowledgePoint2, pk=kp2_id)
    choice_qs = ChoiceProblem.objects.filter(knowledgePoint2=kp2).order_by('-id')
    ducheng_qs = DuchengProblem.objects.filter(knowledgePoint2=kp2).order_by('-ducheng_id')
    all_courses = ClassName.objects.all()
    return render(request, 'quiz/teacher_kp_questions.html', {'title': '%s - 题目列表' % kp2.name, 'position': 'quiz_teacher_kp_manage', 'kp2': kp2, 'choice_questions': choice_qs, 'ducheng_questions': ducheng_qs, 'all_courses': all_courses})
