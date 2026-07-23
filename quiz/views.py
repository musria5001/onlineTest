from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db.models import Count, Sum

from judge.models import ClassName, KnowledgePoint1, KnowledgePoint2, ChoiceProblem, DuchengProblem
from work.models import BanJi
from .models import AnswerRecord, QuizAssignment


@login_required
def kp_tree(request):
    """知识点浏览树：ClassName → KnowledgePoint1 → KnowledgePoint2"""
    if request.user.isTeacher():
        raise Http404()

    courses = ClassName.objects.all().prefetch_related('knowledgepoint1_set__knowledgepoint2_set')
    answered_choice_ids = set(
        AnswerRecord.objects.filter(user=request.user, question_type='choice').values_list('choice_question_id', flat=True)
    )
    answered_ducheng_ids = set(
        AnswerRecord.objects.filter(user=request.user, question_type='ducheng').values_list('ducheng_question_id', flat=True)
    )

    course_data = []
    for course in courses:
        kp1_list = []
        for idx, kp1 in enumerate(course.knowledgepoint1_set.all()):
            kp2_list = []
            kp1_correct = 0
            kp1_answered = 0
            kp1_total = 0
            prev_complete = True
            for kp2 in kp1.knowledgepoint2_set.all():
                choice_count = ChoiceProblem.objects.filter(knowledgePoint2=kp2).count()
                ducheng_count = DuchengProblem.objects.filter(knowledgePoint2=kp2).count()
                total = choice_count + ducheng_count
                # 3轮进度
                all_recs = AnswerRecord.objects.filter(user=request.user, kp2=kp2)
                total_points = all_recs.aggregate(s=Sum('points'))['s'] or 0
                completed_rounds = 0
                if total > 0:
                    from collections import Counter
                    qpr = {}
                    for r in all_recs:
                        qid = r.choice_question_id if r.question_type == 'choice' else r.ducheng_question_id
                        qpr.setdefault(r.round_num, set()).add(qid)
                    completed_rounds = sum(1 for r, qs in qpr.items() if len(qs) >= total)
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
            if kp2_list:
                kp1_list.append({
                    'id': kp1.id, 'name': kp1.name, 'kp2s': kp2_list,
                    'index': idx + 1,
                    'total_correct': kp1_correct,
                    'total_answered': kp1_answered,
                    'total_qs': kp1_total,
                    'show_ellipsis': False,
                })
        # 超过3章时：只显示前3章 + 省略号
        if len(kp1_list) > 3:
            for i, kp1_item in enumerate(kp1_list):
                kp1_item['hidden'] = (i >= 3)  # 第4个及之后隐藏
            kp1_list[2]['show_ellipsis'] = True
            kp1_list[2]['remaining'] = len(kp1_list) - 3
        if kp1_list:
            course_data.append({'id': course.id, 'name': course.name, 'kp1s': kp1_list})

    total_points = AnswerRecord.objects.filter(user=request.user, is_correct=True).count()

    return render(request, 'quiz/kp_tree.html', {
        'title': '选择知识点',
        'position': 'quiz_kp_tree',
        'course_data': course_data,
        'total_points': total_points,
    })


@login_required
def answer_question(request, kp2_id):
    """逐题答题页面"""
    if request.user.isTeacher():
        raise Http404()

    kp2 = get_object_or_404(KnowledgePoint2, pk=kp2_id)
    assignment_id = request.GET.get('assignment')

    # 当前轮次：已完成轮数 + 1
    all_records = AnswerRecord.objects.filter(user=request.user, kp2=kp2)
    total_qs = ChoiceProblem.objects.filter(knowledgePoint2=kp2).count() + DuchengProblem.objects.filter(knowledgePoint2=kp2).count()
    if total_qs == 0:
        return render(request, 'quiz/kp2_complete.html', {
            'title': kp2.name, 'position': 'quiz_kp_tree', 'kp2': kp2,
            'correct': 0, 'total': 0, 'round': 0, 'max_rounds': 3,
            'assignment_id': assignment_id,
        })

    # 已完成轮次
    from collections import Counter
    q_per_round = {}  # round -> set of question ids
    for r in all_records:
        qid = r.choice_question_id if r.question_type == 'choice' else r.ducheng_question_id
        q_per_round.setdefault(r.round_num, set()).add(qid)

    completed_rounds = sum(1 for r, qs in q_per_round.items() if len(qs) >= total_qs)
    current_round = completed_rounds + 1

    if completed_rounds >= 3:
        total_points = all_records.aggregate(s=Sum('points'))['s'] or 0
        return render(request, 'quiz/kp2_complete.html', {
            'title': kp2.name, 'position': 'quiz_kp_tree', 'kp2': kp2,
            'correct': total_points, 'total': 3, 'round': 3, 'max_rounds': 3,
            'assignment_id': assignment_id,
        })

    # 当前轮已正确答过的题
    cur_correct = q_per_round.get(current_round, set())

    # 选未答或本轮错过的题（排除本轮已正确的）
    choice_available = ChoiceProblem.objects.filter(knowledgePoint2__id=kp2_id).exclude(id__in=cur_correct)
    ducheng_available = DuchengProblem.objects.filter(knowledgePoint2__id=kp2_id).exclude(ducheng_id__in=cur_correct)

    import random
    available_pool = []
    if choice_available.exists():
        available_pool.append(('choice', list(choice_available)))
    if ducheng_available.exists():
        available_pool.append(('ducheng', list(ducheng_available)))

    if not available_pool:
        # 当前轮所有题都答对了 → 本轮完成
        completed_rounds = current_round
        if completed_rounds >= 3:
            total_points = all_records.aggregate(s=Sum('points'))['s'] or 0
            return render(request, 'quiz/kp2_complete.html', {
                'title': kp2.name, 'position': 'quiz_kp_tree', 'kp2': kp2,
                'correct': total_points, 'total': 3, 'round': 3, 'max_rounds': 3,
                'assignment_id': assignment_id,
            })
        # 进入下一轮
        current_round = completed_rounds + 1
        # 重新选池
        choice_available = ChoiceProblem.objects.filter(knowledgePoint2__id=kp2_id)
        ducheng_available = DuchengProblem.objects.filter(knowledgePoint2__id=kp2_id)
        available_pool = []
        if choice_available.exists():
            available_pool.append(('choice', list(choice_available)))
        if ducheng_available.exists():
            available_pool.append(('ducheng', list(ducheng_available)))

    qtype, pool = random.choice(available_pool)
    question = random.choice(pool)

    if qtype == 'ducheng':
        return render(request, 'quiz/answer_ducheng.html', {
            'title': kp2.name, 'position': 'quiz_kp_tree', 'kp2': kp2,
            'question': question,
            'progress': {'round': current_round, 'max_rounds': 3, 'completed': completed_rounds},
            'assignment_id': assignment_id,
        })

    return render(request, 'quiz/answer.html', {
        'title': kp2.name, 'position': 'quiz_kp_tree', 'kp2': kp2,
        'question': question,
        'progress': {'round': current_round, 'max_rounds': 3, 'completed': completed_rounds},
        'assignment_id': assignment_id,
    })


@login_required
def submit_answer(request, kp2_id):
    """AJAX 提交答案"""
    if request.user.isTeacher():
        raise Http404()

    kp2 = get_object_or_404(KnowledgePoint2, pk=kp2_id)
    qtype = request.POST.get('question_type', 'choice')
    assignment_id = request.POST.get('assignment_id')

    if qtype == 'choice':
        question_id = request.POST.get('question_id')
        selected = request.POST.get('selected', '').strip().lower()
        if not question_id or selected not in ('a', 'b', 'c', 'd'):
            return JsonResponse({'error': '参数错误'}, status=400)
        question = get_object_or_404(ChoiceProblem, pk=question_id)
        if not question.knowledgePoint2.filter(pk=kp2_id).exists():
            return JsonResponse({'error': '题目不属于该知识点'}, status=400)
        is_correct = (selected == question.right_answer)

        # 首次答错 → 给一次重试机会，不记录
        is_retry = request.POST.get('retry') == '1'
        if not is_correct and not is_retry:
            return JsonResponse({
                'correct': False, 'qtype': 'choice', 'retry': True,
                'msg': '好像回答错误，再思考一下吧',
            })

        # 计算当前轮次
        total_qs = ChoiceProblem.objects.filter(knowledgePoint2=kp2).count() + DuchengProblem.objects.filter(knowledgePoint2=kp2).count()
        all_records = AnswerRecord.objects.filter(user=request.user, kp2=kp2)
        completed_rounds = 0
        from collections import Counter
        q_per_round = {}
        for r in all_records:
            qid = r.choice_question_id if r.question_type == 'choice' else r.ducheng_question_id
            q_per_round.setdefault(r.round_num, set()).add(qid)
        completed_rounds = sum(1 for r, qs in q_per_round.items() if len(qs) >= total_qs)
        current_round = completed_rounds + 1

        points = 0.5 if is_retry and is_correct else (1 if is_correct else 0)

        banji = BanJi.objects.filter(students=request.user).first()
        assignment = None
        if assignment_id:
            try:
                assignment = QuizAssignment.objects.get(pk=assignment_id)
            except QuizAssignment.DoesNotExist:
                pass

        AnswerRecord.objects.create(
            user=request.user, question_type='choice',
            choice_question=question, kp2=kp2, banji=banji,
            assignment=assignment, is_correct=is_correct,
            points=points, round_num=current_round,
            student_answer=selected,
        )
        return JsonResponse({
            'correct': is_correct, 'qtype': 'choice',
            'right_answer': question.right_answer, 'selected': selected,
        })

    else:  # ducheng
        question_id = request.POST.get('question_id')
        student_answer = request.POST.get('selected', '').strip()
        if not question_id or not student_answer:
            return JsonResponse({'error': '请输入答案'}, status=400)
        question = get_object_or_404(DuchengProblem, pk=question_id)
        if not question.knowledgePoint2.filter(pk=kp2_id).exists():
            return JsonResponse({'error': '题目不属于该知识点'}, status=400)

        correct_answers = [a.strip() for a in question.answer.split('|||') if a.strip()]
        is_correct = student_answer in correct_answers

        # 首次答错 → 给一次重试机会
        is_retry = request.POST.get('retry') == '1'
        if not is_correct and not is_retry:
            return JsonResponse({
                'correct': False, 'qtype': 'ducheng', 'retry': True,
                'msg': '好像回答错误，再思考一下吧',
            })

        # 计算当前轮次
        total_qs = ChoiceProblem.objects.filter(knowledgePoint2=kp2).count() + DuchengProblem.objects.filter(knowledgePoint2=kp2).count()
        all_records = AnswerRecord.objects.filter(user=request.user, kp2=kp2)
        from collections import Counter
        q_per_round = {}
        for r in all_records:
            qid = r.choice_question_id if r.question_type == 'choice' else r.ducheng_question_id
            q_per_round.setdefault(r.round_num, set()).add(qid)
        completed_rounds = sum(1 for r, qs in q_per_round.items() if len(qs) >= total_qs)
        current_round = completed_rounds + 1

        points = 0.5 if is_retry and is_correct else (1 if is_correct else 0)

        banji = BanJi.objects.filter(students=request.user).first()
        assignment = None
        if assignment_id:
            try:
                assignment = QuizAssignment.objects.get(pk=assignment_id)
            except QuizAssignment.DoesNotExist:
                pass

        AnswerRecord.objects.create(
            user=request.user, question_type='ducheng',
            ducheng_question=question, kp2=kp2, banji=banji,
            assignment=assignment, is_correct=is_correct,
            points=points, round_num=current_round,
            student_answer=student_answer,
        )
        return JsonResponse({
            'correct': is_correct, 'qtype': 'ducheng',
            'right_answer': question.answer, 'selected': student_answer,
        })


@login_required
def my_points(request):
    """我的积分页"""
    if request.user.isTeacher():
        raise Http404()

    all_my = AnswerRecord.objects.filter(user=request.user)
    total_correct = all_my.filter(is_correct=True).count()
    total_answered = all_my.count()
    total_points = int(all_my.aggregate(s=Sum('points'))['s'] or 0)
    accuracy = round(total_correct * 100 / total_answered, 1) if total_answered > 0 else 0

    # 按二级知识点汇总
    kp2_data = []
    all_kp2s = KnowledgePoint2.objects.filter(answerrecord__user=request.user).distinct()
    for kp2 in all_kp2s:
        correct = AnswerRecord.objects.filter(user=request.user, kp2=kp2, is_correct=True).count()
        total = AnswerRecord.objects.filter(user=request.user, kp2=kp2).count()
        kp2_data.append({
            'name': kp2.name,
            'kp1_name': kp2.upperPoint.name if kp2.upperPoint else '',
            'correct': correct,
            'total': total,
        })

    return render(request, 'quiz/my_points.html', {
        'title': '我的积分',
        'position': 'quiz_points',
        'total_points': total_points,
        'total_answered': total_answered,
        'total_correct': total_correct,
        'accuracy': accuracy,
        'kp2_data': kp2_data,
    })


@login_required
def leaderboard(request):
    """班级积分排行榜"""
    if request.user.isTeacher():
        raise Http404()

    # 获取学生所在的班级
    my_banjis = BanJi.objects.filter(students=request.user)

    banji_rankings = []
    student_group = Group.objects.get(name='学生')
    for banji in my_banjis:
        student_ids = banji.students.filter(groups=student_group).values_list('id', flat=True)
        # 同班学生按积分排名
        rankings = AnswerRecord.objects.filter(
            user__in=student_ids
        ).values(
            'user__username', 'user__id_num', 'user_id'
        ).annotate(
            points=Sum('points')
        ).order_by('-points')

        # 计算当前学生的排名
        my_rank = None
        my_points_val = None
        for idx, row in enumerate(rankings):
            row['rank'] = idx + 1
            if row['user_id'] == request.user.id:
                my_rank = idx + 1
                my_points_val = row['points']

        banji_rankings.append({
            'banji_name': banji.name,
            'rankings': rankings[:50],  # 只取前50
            'my_rank': my_rank,
            'my_points': my_points_val,
            'total_students': rankings.count(),
        })

    return render(request, 'quiz/leaderboard.html', {
        'title': '积分排行榜',
        'position': 'quiz_leaderboard',
        'banji_rankings': banji_rankings,
    })


# ========== 教师端 ==========

@login_required
def teacher_dashboard(request):
    """教师查看所管班级的答题统计"""
    if not request.user.isTeacher():
        raise Http404()

    student_group = Group.objects.get(name='学生')
    banjis = BanJi.objects.filter(teacher=request.user)
    banji_data = []
    for bj in banjis:
        # 只统计学生分组的人
        student_ids = bj.students.filter(groups=student_group).values_list('id', flat=True)
        student_count = len(student_ids)
        # 班级总答题数（只算学生）
        total_answered = AnswerRecord.objects.filter(banji=bj, user__in=student_ids).count()
        total_correct = AnswerRecord.objects.filter(banji=bj, user__in=student_ids, is_correct=True).count()
        # 有多少学生参与过答题
        active_count = AnswerRecord.objects.filter(banji=bj, user__in=student_ids).values('user').distinct().count()
        banji_data.append({
            'id': bj.id,
            'name': bj.name,
            'student_count': student_count,
            'active_count': active_count,
            'total_answered': total_answered,
            'total_correct': total_correct,
            'correct_rate': round(total_correct * 100 / total_answered, 1) if total_answered > 0 else 0,
        })

    return render(request, 'quiz/teacher_dashboard.html', {
        'title': '答题统计',
        'position': 'quiz_teacher_dashboard',
        'banji_data': banji_data,
    })


@login_required
def teacher_class_progress(request, banji_id):
    """查看某个班级所有学生的知识点答题进度"""
    if not request.user.isTeacher():
        raise Http404()

    banji = get_object_or_404(BanJi, pk=banji_id)
    # 确保只有该班的教师能查看
    if banji.teacher != request.user and not request.user.is_superuser:
        raise Http404()

    students = banji.students.filter(groups=Group.objects.get(name='学生'))
    # 获取所有二级知识点
    all_kp2s = KnowledgePoint2.objects.all()

    student_data = []
    for stu in students:
        total_correct = AnswerRecord.objects.filter(user=stu, banji=banji, is_correct=True).count()
        total_answered = AnswerRecord.objects.filter(user=stu, banji=banji).count()
        student_data.append({
            'id': stu.id,
            'username': stu.username,
            'id_num': stu.id_num,
            'total_correct': total_correct,
            'total_answered': total_answered,
        })

    # 按积分降序排
    student_data.sort(key=lambda x: x['total_correct'], reverse=True)

    return render(request, 'quiz/teacher_class_progress.html', {
        'title': '%s - 答题进度' % banji.name,
        'position': 'quiz_teacher_dashboard',
        'banji': banji,
        'student_data': student_data,
        'kp2_count': all_kp2s.count(),
    })


@login_required
def teacher_student_records(request, banji_id, user_id):
    """查看某个学生的详细答题记录"""
    if not request.user.isTeacher():
        raise Http404()

    banji = get_object_or_404(BanJi, pk=banji_id)
    if banji.teacher != request.user and not request.user.is_superuser:
        raise Http404()

    from auth_system.models import MyUser
    stu = get_object_or_404(MyUser, pk=user_id)

    records = AnswerRecord.objects.filter(
        user=stu, banji=banji
    ).select_related('question', 'kp2', 'kp2__upperPoint').order_by('-created_time')[:200]

    # 按知识点汇总
    kp2_summary = []
    kp2_ids = records.values_list('kp2', flat=True).distinct()
    for kp2_id in kp2_ids:
        kp2 = KnowledgePoint2.objects.get(pk=kp2_id)
        correct = records.filter(kp2=kp2, is_correct=True).count()
        total = records.filter(kp2=kp2).count()
        kp2_summary.append({
            'name': kp2.name,
            'kp1_name': kp2.upperPoint.name if kp2.upperPoint else '',
            'correct': correct,
            'total': total,
        })

    tc = records.filter(is_correct=True).count()
    tn = records.count()

    return render(request, 'quiz/teacher_student_records.html', {
        'title': '%s - 答题记录' % stu.username,
        'position': 'quiz_teacher_dashboard',
        'banji': banji,
        'stu': stu,
        'records': records,
        'kp2_summary': kp2_summary,
        'total_correct': tc,
        'total_count': tn,
        'total_wrong': tn - tc,
    })


# ========== 教师端 — 布置作业 ==========

@login_required
def teacher_assignment_create(request):
    """教师布置知识点作业"""
    if not request.user.isTeacher():
        raise Http404()

    if request.method == 'POST':
        banji_id = request.POST.get('banji_id')
        kp2_id = request.POST.get('kp2_id')
        title = request.POST.get('title', '').strip()
        choice_count = int(request.POST.get('choice_count', 0) or 0)
        ducheng_count = int(request.POST.get('ducheng_count', 0) or 0)
        deadline = request.POST.get('deadline') or None

        banji = get_object_or_404(BanJi, pk=banji_id)
        if banji.teacher != request.user and not request.user.is_superuser:
            raise Http404()
        kp2 = get_object_or_404(KnowledgePoint2, pk=kp2_id)

        if deadline:
            from django.utils.dateparse import parse_datetime
            deadline = parse_datetime(deadline)

        QuizAssignment.objects.create(
            title=title or '%s - %s' % (banji.name, kp2.name),
            teacher=request.user,
            banji=banji,
            kp2=kp2,
            choice_count=choice_count,
            ducheng_count=ducheng_count,
            question_count=choice_count + ducheng_count,
            deadline=deadline,
        )
        return JsonResponse({'ok': True})

    # GET — 返回可选的班级和知识点
    banjis = BanJi.objects.filter(teacher=request.user)
    kp2s = KnowledgePoint2.objects.all().select_related('upperPoint__classname')

    kp2_data = []
    for kp2 in kp2s:
        c = ChoiceProblem.objects.filter(knowledgePoint2=kp2).count()
        d = DuchengProblem.objects.filter(knowledgePoint2=kp2).count()
        if c + d > 0:
            kp2_data.append({
                'id': kp2.id,
                'name': kp2.name,
                'kp1_name': kp2.upperPoint.name,
                'course_name': kp2.upperPoint.classname.name,
                'choice_total': c,
                'ducheng_total': d,
                'total': c + d,
            })

    return render(request, 'quiz/teacher_assignment_create.html', {
        'title': '布置作业',
        'position': 'quiz_teacher_assignment_create',
        'banjis': banjis,
        'kp2_data': kp2_data,
    })


@login_required
def teacher_assignment_list(request):
    """教师查看已布置的作业"""
    if not request.user.isTeacher():
        raise Http404()

    assignments = QuizAssignment.objects.filter(teacher=request.user).select_related('banji', 'kp2').order_by('-created_time')
    data = []
    for a in assignments:
        completed = AnswerRecord.objects.filter(assignment=a).values('user').distinct().count()
        total_students = a.banji.students.filter(groups=Group.objects.get(name='学生')).count()
        data.append({
            'id': a.id,
            'title': a.title,
            'banji_name': a.banji.name,
            'kp2_name': a.kp2.name,
            'question_count': a.question_count,
            'deadline': a.deadline,
            'completed': completed,
            'total_students': total_students,
        })

    return render(request, 'quiz/teacher_assignment_list.html', {
        'title': '已布置作业',
        'position': 'quiz_teacher_assignment_list',
        'assignments': data,
    })


@login_required
def teacher_assignment_delete(request, assignment_id):
    """教师删除已布置的作业"""
    if not request.user.isTeacher():
        raise Http404()
    a = get_object_or_404(QuizAssignment, pk=assignment_id)
    if a.teacher != request.user and not request.user.is_superuser:
        raise Http404()
    a.delete()
    return JsonResponse({'ok': True})


# ========== 学生端 — 作业列表 ==========

@login_required
def student_assignments(request):
    """学生查看待完成的作业"""
    if request.user.isTeacher():
        raise Http404()

    my_banjis = BanJi.objects.filter(students=request.user)
    assignments = QuizAssignment.objects.filter(banji__in=my_banjis).select_related('teacher', 'kp2', 'kp2__upperPoint').order_by('-created_time')

    data = []
    for a in assignments:
        answered = AnswerRecord.objects.filter(user=request.user, kp2=a.kp2, banji=a.banji, assignment=a).count()
        data.append({
            'id': a.id,
            'title': a.title,
            'teacher_name': a.teacher.username,
            'kp2_id': a.kp2_id,
            'kp2_name': a.kp2.name,
            'question_count': a.question_count,
            'choice_count': a.choice_count,
            'ducheng_count': a.ducheng_count,
            'answered': answered,
            'deadline': a.deadline,
            'complete': answered >= a.question_count,
        })

    return render(request, 'quiz/student_assignments.html', {
        'title': '我的作业',
        'position': 'quiz_student_assignments',
        'assignments': data,
    })


# ========== 教师端 — 知识点管理（加题） ==========

@login_required
def teacher_kp_manage(request):
    """教师管理知识点下的题目"""
    if not request.user.isTeacher():
        raise Http404()

    kp2s = KnowledgePoint2.objects.all().select_related('upperPoint__classname')
    kp2_data = []
    for kp2 in kp2s:
        total = ChoiceProblem.objects.filter(knowledgePoint2=kp2).count()
        kp2_data.append({
            'id': kp2.id,
            'name': kp2.name,
            'kp1_name': kp2.upperPoint.name,
            'course_name': kp2.upperPoint.classname.name,
            'total': total,
        })
    return render(request, 'quiz/teacher_kp_manage.html', {
        'title': '知识点管理',
        'position': 'quiz_teacher_kp_manage',
        'kp2_data': kp2_data,
    })


@login_required
def teacher_kp_questions(request, kp2_id):
    """查看某个知识点下的题目列表（选择题+填空题）"""
    if not request.user.isTeacher():
        raise Http404()

    kp2 = get_object_or_404(KnowledgePoint2, pk=kp2_id)
    choice_qs = ChoiceProblem.objects.filter(knowledgePoint2=kp2).order_by('-id')
    ducheng_qs = DuchengProblem.objects.filter(knowledgePoint2=kp2).order_by('-ducheng_id')
    all_courses = ClassName.objects.all()

    return render(request, 'quiz/teacher_kp_questions.html', {
        'title': '%s - 题目管理' % kp2.name,
        'position': 'quiz_teacher_kp_manage',
        'kp2': kp2,
        'choice_questions': choice_qs,
        'ducheng_questions': ducheng_qs,
        'all_courses': all_courses,
    })


@login_required
def teacher_add_question(request, kp2_id):
    """AJAX：向某知识点添加新题目"""
    if not request.user.isTeacher():
        raise Http404()

    kp2 = get_object_or_404(KnowledgePoint2, pk=kp2_id)
    qtype = request.POST.get('question_type', 'choice')

    if qtype == 'choice':
        title = request.POST.get('title', '').strip()
        a = request.POST.get('a', '').strip()
        b = request.POST.get('b', '').strip()
        c = request.POST.get('c', '').strip()
        d = request.POST.get('d', '').strip()
        right = request.POST.get('right', '').strip()

        if not all([title, a, b, c, d, right]) or right not in 'abcd':
            return JsonResponse({'ok': False, 'msg': '请填写所有选项，正确答案为 a/b/c/d'})

        q = ChoiceProblem.objects.create(
            title=title, a=a, b=b, c=c, d=d,
            right_answer=right, creater=request.user,
        )
        q.knowledgePoint2.add(kp2)
        q.knowledgePoint1.add(kp2.upperPoint)
        q.classname.add(kp2.upperPoint.classname)

    else:  # ducheng
        title = request.POST.get('title', '').strip()
        answer = request.POST.get('answer', '').strip()
        if not title or not answer:
            return JsonResponse({'ok': False, 'msg': '请填写题干和答案'})

        q = DuchengProblem.objects.create(
            title=title, answer=answer, creater=request.user,
        )
        q.knowledgePoint2.add(kp2)
        q.knowledgePoint1.add(kp2.upperPoint)
        q.classname.add(kp2.upperPoint.classname)

    return JsonResponse({'ok': True, 'id': q.id, 'qtype': qtype})


@login_required
def teacher_link_questions(request, kp2_id):
    """AJAX：从题库批量导入已有题目到知识点"""
    if not request.user.isTeacher():
        raise Http404()

    kp2 = get_object_or_404(KnowledgePoint2, pk=kp2_id)
    ids = request.POST.get('ids', '').strip().split(',')
    qtype = request.POST.get('question_type', 'choice')
    count = 0

    for pid in ids:
        pid = pid.strip()
        if not pid:
            continue
        try:
            pid = int(pid)
        except ValueError:
            continue

        if qtype == 'choice':
            q = ChoiceProblem.objects.get(pk=pid)
            q.knowledgePoint2.add(kp2)
            q.knowledgePoint1.add(kp2.upperPoint)
            q.classname.add(kp2.upperPoint.classname)
        else:
            q = DuchengProblem.objects.get(pk=pid)
            q.knowledgePoint2.add(kp2)
            q.knowledgePoint1.add(kp2.upperPoint)
            q.classname.add(kp2.upperPoint.classname)
        count += 1

    return JsonResponse({'ok': True, 'count': count})


@login_required
def teacher_ajax_kp1s(request):
    """AJAX：教师端返回某课程下的一级知识点"""
    if not request.user.isTeacher(): raise Http404()
    cid = request.GET.get('course_id', '')
    if not cid: return JsonResponse({})
    kp1s = KnowledgePoint1.objects.filter(classname_id=cid)
    return JsonResponse({kp1.id: kp1.name for kp1 in kp1s})


@login_required
def teacher_ajax_kp2s(request):
    """AJAX：教师端返回某一级知识点下的二级知识点"""
    if not request.user.isTeacher(): raise Http404()
    kid = request.GET.get('kp1_id', '')
    if not kid: return JsonResponse({})
    kp2s = KnowledgePoint2.objects.filter(upperPoint_id=kid)
    return JsonResponse({kp2.id: kp2.name for kp2 in kp2s})


@login_required
def teacher_search_questions(request):
    """AJAX：搜索题库中未关联的题目"""
    if not request.user.isTeacher():
        raise Http404()

    qtype = request.GET.get('type', 'choice')
    q = request.GET.get('q', '').strip()
    kp2_id = request.GET.get('kp2_id', '')
    filter_kp2 = request.GET.get('filter_kp2', '')

    if qtype == 'choice':
        qs = ChoiceProblem.objects.all()
        if filter_kp2:
            qs = qs.filter(knowledgePoint2__id=filter_kp2)
        if q:
            qs = qs.filter(title__icontains=q)
        if kp2_id:
            qs = qs.exclude(knowledgePoint2__id=kp2_id)
        results = [{'id': r.id, 'title': r.title[:60], 'answer': r.right_answer} for r in qs[:30]]
    else:
        qs = DuchengProblem.objects.all()
        if filter_kp2:
            qs = qs.filter(knowledgePoint2__id=filter_kp2)
        if q:
            qs = qs.filter(title__icontains=q)
        if kp2_id:
            qs = qs.exclude(knowledgePoint2__id=kp2_id)
        results = [{'id': r.ducheng_id, 'title': r.title[:60], 'answer': r.answer[:30]} for r in qs[:30]]

    return JsonResponse({'results': results})


@login_required
def teacher_delete_question(request, question_id):
    """AJAX：删除某道题（支持选择和填空）"""
    if not request.user.isTeacher():
        raise Http404()
    qtype = request.GET.get('type', 'choice')
    if qtype == 'choice':
        q = get_object_or_404(ChoiceProblem, pk=question_id)
    else:
        q = get_object_or_404(DuchengProblem, pk=question_id)
    if q.creater != request.user and not request.user.is_superuser:
        return JsonResponse({'ok': False, 'msg': '只能删除自己创建的题目'})
    q.delete()
    return JsonResponse({'ok': True})
