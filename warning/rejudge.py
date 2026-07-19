from work.models import MyHomework, HomeworkAnswer
from work.views import judge_homework
from judge.models import SourceCode
import _thread
import datetime

#import os,django
#os.environ.setdefault("DJANGO_SETTINGS_MODULE", "onlineTest.settings")# project_name 项目名称
#django.setup()

def part1():
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" 开始补判作业服务...")
    answers = HomeworkAnswer.objects.all().filter(judged=0)
    print("共有{}份作业需要补判".format(len(answers)))
    for i in answers:
        #if i.score and i.score != i.homework.total_score:
        if i.judged==0:
            skip = False
            print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+' judging HomeworkAnswerID:' + str(i.id))
            for j in i.solution_set.all():
                if not j:
                    skip = True
                    break
                if j.result in [0, 1, 2, 3]:
                    if SourceCode.objects.all().filter(solution_id=j.solution_id):
                        j.result = 0
                        j.save()
                    else:
                        skip = True
                        break
            if not skip:
                judge_homework(i)
            else:
                i.judged==1
                i.save()
            print('...OK')
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" 结束补判作业服务")

def part2():
    print('part 2')
    from work.models import MyHomework, HomeworkAnswer

    homework = MyHomework.objects.get(pk=175)
    for i in homework.homeworkanswer_set.all():
        for j in i.solution_set.all():
            judge_homework(i)
            print('judged' + str(j.pk))

def part3():
    print('part3')
    from work.models import MyHomework
    import json

    for i in MyHomework.objects.all():
        try:
            for info in json.loads(i.problem_info):
                try:
                    for case in info['testcases']:  # 获取题目的测试分数
                        if case['desc']:
                            pass
                except Exception as e:
                    print("error on get problem score :" + str(i.pk) + str(e))
        except:
            print("error encode " + str(i.pk))

# part1()
