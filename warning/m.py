# -*- coding:utf-8 -*-
from auth_system.models import MyUser
from onlineTest.settings import USER_FILE_DIR
from work.models import BanJi,MyHomework,HomeworkAnswer
from judge.models import ChoiceProblem
from warning.models import WarningData
from sign.models import Event, Sign
import re
import datetime
import os
import json
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from warning import gcp
from django.utils import timezone
import xlrd,xlwt

from message.views import createMsg
from message.models import Message

now = datetime.datetime.now()
homeworkstarttime= now - datetime.timedelta(days=30)
homeworkendtime=now + datetime.timedelta(days=7)
domain = settings.SITE_DOMAIN

def getAllTeachers():    
    return MyUser.objects.filter(groups__pk='1')

def getBanjiofTeacher(id):
    return BanJi.objects.filter(teacher_id=id).filter(end_time__gte = now)

def getMyHomeworkList(id):
    return MyHomework.objects.filter(start_time__gte = homeworkstarttime).filter(end_time__lte = homeworkendtime).filter(banji__id=id)

def getStudentsList(banjiid,teacherid):
    return BanJi.objects.filter(id=banjiid).first().students.all().exclude(id=teacherid)

def getChoiceInfoListByIds(ids):
    return ChoiceProblem.objects.in_bulk(ids)

def getGoodAndBadStu(stuids,homeworkid):
    goodstu = ''
    badstu = ''
    sql = "creator_id in ("
    for id in stuids:
        sql = sql + str(id) + ','
    sql = sql[:-1] + ')'
    res = HomeworkAnswer.objects.extra(where=[sql]).filter(homework_id=homeworkid).order_by('-score','create_time')
    if len(res) > 5:
        for i in res[:5]:
            goodstu = goodstu + i.creator.username + "(" + i.creator.id_num + ":" + str(i.score) + "分); "
        for i in res.reverse()[:5]:
            if i.score < i.homework.total_score:
                badstu = badstu + i.creator.username + "(" + i.creator.id_num + ":" + str(i.score) + "分);"
    return goodstu,badstu


def getDict():
    path = '/home/judge/log/'
    files = os.listdir(path)
    resultdict={}
    for file in files:
        if file.find("detail")!=0:
            continue
        #print(file)
        f = open(path+file,'r',encoding="UTF-8")        
        for line in f:
            if line[:2] == ">>":
                logtime = datetime.datetime.strptime(line[3:22],"%Y-%m-%d %H:%M:%S")
                if logtime >= homeworkstarttime:
                    if(re.search('提交',line)):
                        s=re.findall(r"selection-\d+': '[a-d]",line)
                        d = {}
                        if s:
                            for one in s:
                                d[re.search(r'\d+',one).group()] =  one[-1]                                    
                        a=re.split(":|\：|\(|\)|\，",line)
                        key = a[8]+a[11]
                        item=[]
                        if key in resultdict:
                            item = resultdict[key]
                        item.append(d)
                        resultdict[key]=item
    return resultdict



def warning(tea=None):
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" 开始作业预警服务...")
    mydict = getDict()
    teacherList = getAllTeachers()
    for teacher in teacherList:
        if tea!=None and teacher.username!=tea:
            continue
        print("开始准备给",teacher.username,"发送邮件：",flush=True)
        msgteacher = "%s 老师您好:\n"%teacher.username
        banjiList = getBanjiofTeacher(teacher.id)
        msgbanji = ''
        for banji in banjiList:
            print("正在生成班级"+str(banji)+"的数据，包括：",end='',flush=True)
            homeworkList = getMyHomeworkList(banji.id)
            print("{}份作业".format(len(homeworkList)),end='',flush=True)
            studentList = getStudentsList(banji.id,teacher.id)
            print("、{}位同学".format(len(studentList)),flush=True)
            msghomework = ''
            for homework in homeworkList:
                print("正在生成作业"+str(homework)+"的数据:",end='',flush=True)
                print("选择题部分、",end='',flush=True)
                choiceListStr = homework.choice_problem_ids
                choiceidList = []
                choiceinfoList = []
                if choiceListStr != '':
                    choiceidList = re.split(',',choiceListStr)
                    if choiceidList[-1] == '':
                        choiceidList = choiceidList[:-1]
                    choiceinfoList = getChoiceInfoListByIds(choiceidList)
                total = 0
                stuids = []
                goodstu = ""
                badstu = ""
                chwresult = {}
                finishstudentlist = homework.finished_students.all()
                for student in studentList:
                    stuids.append(student.id)
                    if student in finishstudentlist:
                        total = total + 1
                        if choiceidList:
                            keyd = str(student.id_num) + str(homework.id)
                            item = mydict.get(keyd,[])
                            for answerdict in item:
                                for key,value in choiceinfoList.items():
                                    chwresult[key] = chwresult.get(key,{'a':0,'b':0,'c':0,'d':0,'w':0,'t':0})
                                    answer = answerdict.get(str(key),None)
                                    if answer:
                                        chwresult[key]['t'] += 1
                                        chwresult[key][answer] += 1
                                        if value.right_answer != answer:
                                            chwresult[key]['w'] += 1
                            if item:
                                del mydict[keyd]
                print("编程题部分、",end='',flush=True)
                copydict = {}
                if stuids:
                    goodstu,badstu = getGoodAndBadStu(stuids,homework.id)
                    copydict = gcp.getCopyGroups(homework.id,stuids)
                print("生成邮件正文",flush=True)
                msghomework = "\n%s 班级的作业《%s》(起止时间：%s--%s) 完成情况如下：\n  全班共有%d人，已交作业%d份。"%(banji.name,homework.name,homework.start_time.strftime("%Y-%m-%d"),homework.end_time.strftime("%Y-%m-%d"),len(studentList),total)
                msghomework = msghomework + " 详情请点击链接查看： http://"+ domain + "/work/my-homework-detail/" + str(homework.id) + "\n"
                if goodstu:
                    msghomework = msghomework + "  成绩较好的同学有:" + goodstu + "\n"
                if badstu:
                    msghomework = msghomework + "  成绩较差的同学有:" + badstu + "\n"
                if chwresult:
                    jsdata = json.dumps(chwresult)
                    w = WarningData(data = jsdata,tid = teacher.id)
                    w.save()                    
                    msghomework = msghomework + "  错误的选择题请点击链接查看（按错误率排序）： http://" + domain + "/warning?id="+ str(w.id) +"\n"
                
                if copydict:
                    msghomework = msghomework + '  依据程序相似度匹配算法，我们发现以下同学的作业相似度较高，请您及时关注是否存在作业抄袭现象：\n'
                    for key in copydict:
                        msghomework = msghomework + '    (' + key + ' ' + copydict[key] + ')\n'

                if msghomework:
                    msgbanji = msgbanji + msghomework
        if msgbanji:
            msgteacher = msgteacher + msgbanji
            sendMailToTeacher(msgteacher,teacher.email)
            print(msgteacher)
            regex = re.compile(r"(https?:\/\/[\w\-\.!~?&=+\*\'(),\/]+)((?!\<\/\a\>).)*")
            msgteacher = regex.sub(lambda m: '<a href={0} target=_blank>{0}</a>'.format(m.group(0)), msgteacher)
            regex = re.compile(r"《.*》|全班共有.*份")
            msgteacher = regex.sub(lambda m: '<font style=color:red>{0}</font>'.format(m.group(0)), msgteacher)
            createMsg(sid=3,rid=teacher.id,message=msgteacher,objId=0,messagetype=0)
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" 结束作业预警服务")

    # 如果是指定给某位老师发邮件，以下任务不做
    if tea!=None:
        return
    # 计算作业成绩
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" 开始作业分析任务...")
    banjiList = BanJi.objects.filter(Q(end_time__gte=timezone.now())&Q(start_time__lte=timezone.now()))
    for banji in banjiList:
        json_data = {}
        records = []
        print("正在分析班级：",banji.name," 的过程数据")
        homeworks = banji.myhomework_set.all().order_by('start_time')
        stuCount = 0
        # 获取慕课成绩表
        try:
            class_id = banji.id
            banji1 = BanJi.objects.get(pk=class_id)
            classname = str(banji1.pk)
            tea_name = banji1.teacher.id_num
            uploadDir = USER_FILE_DIR+'mooc/'+tea_name+'/'+classname+'.xls'
            maxscore=[]
            dstFilename = uploadDir
            excel_path2 = dstFilename
            workbook2 = xlrd.open_workbook(excel_path2)
            sheet2 = workbook2.sheet_by_index(0)
            r_length = sheet2.nrows
            c_length = sheet2.ncols
            #获取慕课单次最大成绩集合
            for col in range(1, c_length):
                try:
                    max_score=sheet2.cell_value(1, col)
                except IndexError:
                    break 
                if max_score is not None and max_score!="" and max_score!="无":
                    maxscore.append(float(max_score))
                else:
                    st_score=[]
                    for i in range (2, r_length):
                        st_score.append(sheet2.cell_value(i, col) if str(sheet2.cell_value(i, col)) not in '无-' else '0')
                    st_score=[ int(float(x)) for x in st_score ]
                    maxscore.append(max(st_score))
            maxscore=[ int(float(x)) for x in maxscore ]
        except FileNotFoundError:
            print('获取慕课成绩文件', uploadDir, '失败')
        for student in banji.students.all().order_by('id_num'):
            #筛除教师账号
            if student.groups.all()[0].pk==2 :
                count = 1
                record = {'id': student.id_num,
                          'name': student.username,
                          'studentId': student.id}
                # 统计签到情况
                timeNow = datetime.datetime.now()
                events = Event.objects.filter(banji=banji,started_time__lte=timeNow)
                sign_count = len(events)
                signed_count = 0
                for event in events:
                    sign = Sign.objects.filter(event=event,user=student.id)
                    if len(sign)>0:
                        signed_count = signed_count + 1
                record['signedCount'] = signed_count
                record['signCount'] = sign_count
                # 计算慕课成绩
                average_mscore = 0.0
                if len(maxscore)>0:
                    moocScore = 0.0
                    for k in range(1, c_length):
                        for i in range(0, r_length):
                            if student.id_num in sheet2.cell_value(i, 0):
                                if str(sheet2.cell_value(i, k)) not in '无-':
                                    moocScore = moocScore + float(sheet2.cell_value(i, k))
                                break
                    record['moocScore'] = moocScore
                    average_mscore = 0.0
                    s_score=[]
                    for row in range(0, r_length):
                        if student.id_num in sheet2.cell_value(row, 0):
                            for col in range(1, c_length):
                                s_score.append(sheet2.cell_value(row, col))
                            s_score=[0 if str(i) in '无-' else i for i in s_score]
                            s_score=[ int(float(x)) for x in s_score ]
                            s_score=list(map(lambda x,y:x/y,s_score,maxscore))
                            sum=0.0
                            for score in s_score:
                                sum = sum + score
                            average_mscore = sum/len(s_score)
                # 计算作业成绩
                total_pscore = 0
                average_pscore = 0.0
                for index, homework in enumerate(homeworks):
                    answers = homework.homeworkanswer_set.all()
                    answer = answers.filter(creator=student).order_by('-create_time') if student in homework.finished_students.all() else None
                    if answer :
                        answer = answer[0]
                        record['score' + str(count)] = {
                               'pk': answer.pk,
                               'score': answer.score,
                               'work_kind':homework.work_kind
                            }
                        total_pscore += 100 * answer.score / homework.total_score
                    else :
                        record['score' + str(count)] = {
                               'score': "无",
                               'work_kind':homework.work_kind
                            }
                    count = count + 1
                record['total_pscore'] = total_pscore
                average_pscore = 0 if count==1 else total_pscore/100/(count-1)
                # 加权计算排名得分,从班级score_weight中获取权重设置
                score_weight = eval(banji.score_weight)
                pscoreWeight = float(score_weight['pscore'])
                mscoreWeight = float(score_weight['mscore'])
                signWeight = float(score_weight['sign'])
                final_score = 0.0
                score1 = average_pscore*pscoreWeight
                score2 = average_mscore*mscoreWeight
                score3 = 0 if sign_count==0 else (signed_count/sign_count)*signWeight
                final_score = (score1 + score2 + score3)*100
                record['final_score'] = '%.1f' % final_score
                # 保存计算结果
                records.append(record)
                json_data['rows'] = records
                stuCount = stuCount + 1
        json_data['total'] = stuCount
        banji.work_result = json_data
        banji.update_time = datetime.datetime.now()
        banji.save()
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" 结束作业分析任务") 

def sendMailToTeacher(msg,emailaddress,title="作业完成情况反馈"):
    #from_email = settings.EMAIL_HOST_USER

    os.system("echo '%s' | mail -s %s %s -aFrom:%s\<%s\>" % (msg,title,emailaddress,settings.ADMINS[0][0],settings.ADMINS[0][1]))
    #from_email = settings.EMAIL_HOST_USER
    #send_mail(title,msg,from_email,[emailaddress])

from wenda.models import Question,Answer
def getUpdateQuestion():
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" 开始智能问答提醒服务...")
    today = datetime.date.today() 
    new_question = Question.objects.filter(update_date = today)
    message = ''
    q_num = 0
    for q in new_question:
        if not Answer.objects.filter(question=q).exists():
            id_num = q.asker.id_num
            username = q.asker.username
            qus = q.ques
            msg = "%s %s 提问 %s(http://%s/wenda/qusdetail/%d)\n" %(id_num,username,qus,domain,q.id)
            message += msg
            q_num += 1

    title = "%d年%d月%d日，共有%d条新问题未解答" % (today.year,today.month,today.day,q_num)
    sendMailToTeacher(message,settings.ADMINS[0][2],title)
    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+" 结束智能问答提醒服务")
    
