from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db.models import Count, Sum

from judge.models import ClassName, KnowledgePoint1, KnowledgePoint2, ChoiceProblem, DuchengProblem
from work.models import BanJi
from .models import AnswerRecord


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

    # 当前轮次
    all_records = AnswerRecord.objects.filter(user=request.user, kp2=kp2)
    total_qs = ChoiceProblem.objects.filter(knowledgePoint2=kp2).count() + DuchengProblem.objects.filter(knowledgePoint2=kp2).count()
    if total_qs == 0:
        return render(request, 'quiz/kp2_complete.html', {
            'title': kp2.name, 'position': 'quiz_kp_tree', 'kp2': kp2,
            'correct': 0, 'total': 0, 'round': 0, 'max_rounds': 3,
        })

    # 当前工作轮次
    q_per_round = {}
    for r in all_records:
        qid = r.choice_question_id if r.question_type == 'choice' else r.ducheng_question_id
        q_per_round.setdefault(r.round_num, set()).add(qid)

    # 找到第一个未完成的轮次
    show_done = request.GET.get('done')
    work_round = 1
    for rnd in range(1, 4):
        if len(q_per_round.get(rnd, set())) < total_qs:
            work_round = rnd
            break
    else:
        # 全部3轮完成
        total_points = all_records.aggregate(s=Sum('points'))['s'] or 0
        return render(request, 'quiz/kp2_complete.html', {
            'title': kp2.name, 'position': 'quiz_kp_tree', 'kp2': kp2,
            'correct': int(total_points), 'total': 3, 'round': 3, 'max_rounds': 3,
        })

    # 通过 ?done=N 显示刚完成的轮次结算
    if show_done:
        return render(request, 'quiz/kp2_round_done.html', {
            'title': kp2.name, 'position': 'quiz_kp_tree', 'kp2': kp2,
            'round': int(show_done), 'max_rounds': 3,
            'remaining': 3 - int(show_done),
            'kp2': kp2,
        })

    cur_answered = len(q_per_round.get(work_round, set()))

    cur_answered = len(q_per_round.get(work_round, set()))

    # 当前轮正在答题中
    cur_correct = q_per_round.get(work_round, set())

    # 按固定顺序出题（排除本轮已答的）
    choice_available = [q for q in ChoiceProblem.objects.filter(knowledgePoint2__id=kp2_id).order_by('id') if q.id not in cur_correct]
    ducheng_available = [q for q in DuchengProblem.objects.filter(knowledgePoint2__id=kp2_id).order_by('ducheng_id') if q.ducheng_id not in cur_correct]

    available_pool = []
    if choice_available:
        available_pool.append(('choice', choice_available))
    if ducheng_available:
        available_pool.append(('ducheng', ducheng_available))

    # 合并两池按固定顺序（同一个知识点所有学生看到相同题目顺序）
    merged = []
    for qt, pl in available_pool:
        for q in pl:
            merged.append((qt, q))
    # 交替排列：选第1、填第1、选第2、填第2...
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

    # 当前轮已答题数 = 本轮已有记录的去重题目数
    cur_answered = len(q_per_round.get(work_round, set()))
    q_total = total_qs  # 总题数（常量）

    if qtype == 'ducheng':
        return render(request, 'quiz/answer_ducheng.html', {
            'title': kp2.name, 'position': 'quiz_kp_tree', 'kp2': kp2,
            'question': question,
            'progress': {'round': work_round, 'max_rounds': 3,
                         'cur_answered': cur_answered, 'total': q_total},
        })

    return render(request, 'quiz/answer.html', {
        'title': kp2.name, 'position': 'quiz_kp_tree', 'kp2': kp2,
        'question': question,
        'progress': {'round': work_round, 'max_rounds': 3,
                     'cur_answered': cur_answered, 'total': q_total},
    })


@login_required
def submit_answer(request, kp2_id):
    """AJAX 提交答案"""
    if request.user.isTeacher():
        raise Http404()

    kp2 = get_object_or_404(KnowledgePoint2, pk=kp2_id)
    qtype = request.POST.get('question_type', 'choice')
    # assignment feature removed

    if qtype == 'choice':
        question_id = request.POST.get('question_id')
        selected = request.POST.get('selected', '').strip().lower()
        if not question_id or selected not in ('a', 'b', 'c', 'd'):
            return JsonResponse({'error': '参数错误'}, status=400)
        question = get_object_or_404(ChoiceProblem, pk=question_id)
        if not question.knowledgePoint2.filter(pk=kp2_id).exists():
            return JsonResponse({'error': '题目不属于该知识点'}, status=400)
        is_correct = (selected == question.right_answer)

        # 答错 → 原地重试一次
        is_retry = request.POST.get('retry') == '1'
        if not is_correct and not is_retry:
            return JsonResponse({
                'correct': False, 'qtype': 'choice', 'retry': True,
                'msg': '好像回答错误，再思考一下吧',
            })
        # 当前工作轮次 = 已有记录的最高轮次
        total_qs = ChoiceProblem.objects.filter(knowledgePoint2=kp2).count() + DuchengProblem.objects.filter(knowledgePoint2=kp2).count()
        all_records = AnswerRecord.objects.filter(user=request.user, kp2=kp2)
        q_per_round = {}
        for r in all_records:
            qid = r.choice_question_id if r.question_type == 'choice' else r.ducheng_question_id
            q_per_round.setdefault(r.round_num, set()).add(qid)
        work_round = max(q_per_round.keys()) if q_per_round else 1
        # 如果当前轮已完成，进入下一轮
        if len(q_per_round.get(work_round, set())) >= total_qs:
            work_round += 1

        points = 0.5 if (is_retry and is_correct) else (1 if is_correct else 0)

        banji = BanJi.objects.filter(students=request.user).first()

        # 同一轮同一题只保留一条记录
        AnswerRecord.objects.filter(
            user=request.user, question_type='choice',
            choice_question=question, round_num=work_round
        ).delete()

        AnswerRecord.objects.create(
            user=request.user, question_type='choice',
            choice_question=question, kp2=kp2, banji=banji,
            is_correct=is_correct,
            points=points, round_num=work_round,
            student_answer=selected,
        )
        # 检测本轮是否刚完成（统计所有题型）
        done_rnd = None
        cnt_choice = AnswerRecord.objects.filter(user=request.user, kp2=kp2, round_num=work_round, question_type='choice').values('choice_question_id').distinct().count()
        cnt_ducheng = AnswerRecord.objects.filter(user=request.user, kp2=kp2, round_num=work_round, question_type='ducheng').values('ducheng_question_id').distinct().count()
        if cnt_choice + cnt_ducheng >= total_qs:
            done_rnd = work_round

        return JsonResponse({
            'correct': is_correct, 'qtype': 'choice',
            'right_answer': question.right_answer, 'selected': selected,
            'done': done_rnd,
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

        # 答错 → 原地重试一次
        is_retry = request.POST.get('retry') == '1'
        if not is_correct and not is_retry:
            return JsonResponse({
                'correct': False, 'qtype': 'ducheng', 'retry': True,
                'msg': '好像回答错误，再思考一下吧',
            })
        # 记录答题

        # 当前工作轮次 = 已有记录的最高轮次
        total_qs = ChoiceProblem.objects.filter(knowledgePoint2=kp2).count() + DuchengProblem.objects.filter(knowledgePoint2=kp2).count()
        all_records = AnswerRecord.objects.filter(user=request.user, kp2=kp2)
        q_per_round = {}
        for r in all_records:
            qid = r.choice_question_id if r.question_type == 'choice' else r.ducheng_question_id
            q_per_round.setdefault(r.round_num, set()).add(qid)
        work_round = max(q_per_round.keys()) if q_per_round else 1
        if len(q_per_round.get(work_round, set())) >= total_qs:
            work_round += 1

        points = 0.5 if (is_retry and is_correct) else (1 if is_correct else 0)

        banji = BanJi.objects.filter(students=request.user).first()

        # 同一轮同一题只保留一条记录
        AnswerRecord.objects.filter(
            user=request.user, question_type='ducheng',
            ducheng_question=question, round_num=work_round
        ).delete()

        AnswerRecord.objects.create(
            user=request.user, question_type='ducheng',
            ducheng_question=question, kp2=kp2, banji=banji,
            is_correct=is_correct,
            points=points, round_num=work_round,
            student_answer=student_answer,
        )
        cnt_choice = AnswerRecord.objects.filter(user=request.user, kp2=kp2, round_num=work_round, question_type='choice').values('choice_question_id').distinct().count()
        cnt_ducheng = AnswerRecord.objects.filter(user=request.user, kp2=kp2, round_num=work_round, question_type='ducheng').values('ducheng_question_id').distinct().count()
        done_rnd = work_round if (cnt_choice + cnt_ducheng) >= total_qs else None
        return JsonResponse({
            'correct': is_correct, 'qtype': 'ducheng',
            'right_answer': question.answer, 'selected': student_answer,
            'done': done_rnd,
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
    ).select_related('choice_question', 'ducheng_question', 'kp2', 'kp2__upperPoint').order_by('-created_time')[:200]

    # 按知识点汇总
    kp2_summary = []
    kp2_ids = AnswerRecord.objects.filter(user=stu, banji=banji).values_list('kp2', flat=True).distinct()
    base_qs = AnswerRecord.objects.filter(user=stu, banji=banji)
    for kp2_id in kp2_ids:
        kp2 = KnowledgePoint2.objects.get(pk=kp2_id)
        correct = base_qs.filter(kp2=kp2, is_correct=True).count()
        total = base_qs.filter(kp2=kp2).count()
        kp2_summary.append({
            'name': kp2.name,
            'kp1_name': kp2.upperPoint.name if kp2.upperPoint else '',
            'correct': correct,
            'total': total,
        })

    tc = base_qs.filter(is_correct=True).count()
    tn = base_qs.count()

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
