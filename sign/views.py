import os.path, uuid
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.db import connection
from django.db.models import Count
from sign.models import Event, Sign, Leave, Record
from auth_system.models import MyUser
from work.models import BanJi
from django.shortcuts import render
from django.core.paginator import Paginator, EmptyPage
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
from onlineTest.settings import BASE_DIR,USER_FILE_DIR,STATIC_ROOT
from django.contrib.auth.decorators import permission_required, login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.utils.datastructures import MultiValueDictKeyError
import logging, traceback
logger = logging.getLogger('django')
logger_request = logging.getLogger('django.request')

@login_required()
def teacher_index(request):
    user = request.user

    if request.method == 'GET' and user.isTeacher():
        all_student_count = {}

        cursor = connection.cursor()
        classesSql = 'select id, name\
            from work_banji \
            where teacher_id = %d ' % user.id \
            + 'and now() between date_sub(start_time,interval 10 day) and end_time'
        cursor.execute(classesSql)
        classes = list(map(lambda x: dict(zip(['banjiId', 'name'], x)), cursor.fetchall()))[::-1]
        for banji in classes:
            all_student_count[banji['banjiId']] = BanJi.objects.get(id = banji['banjiId']).students.count()-1
        
        eventList = Event.objects.filter(teacher_id=user.id,banji__in=[x['banjiId'] for x in classes]).\
                   prefetch_related('banji').\
                   values('id','has_signed_count','created_time','started_time','closed_time','banji__name','banji__id').\
                   order_by('started_time').all()
        for event in eventList:
            event['all_student_count'] = all_student_count[event['banji__id']]
            count = len(Sign.objects.filter(event=event['id'],type_of=0))
            event['has_signed_count'] = count
            count = len(Sign.objects.filter(event=event['id'],type_of=1,is_checked=0))
            event['has_leave'] = True if count>0 else False

        return render(request, "sign_teacher_index.html", {
            'data': eventList,
            'classes': classes
        })
    else:
        raise PermissionDenied

@csrf_exempt
def create(request):
    user = request.user

    if request.method == 'POST' and user.isTeacher:   #judge HTTP method and user identity
        timeNow = datetime.now()

        position = request.POST.get('position')   #点名发起的位置，以此来判断学生是否在指定范围内签到
        started_time = datetime.strptime(request.POST.get('startedTime'), '%Y-%m-%d %H:%M')     #点名开始的时间，可自定义
        closed_time = datetime.strptime(request.POST.get('closedTime'), '%Y-%m-%d %H:%M')    #点名结束的时间，默认10min的点名期限
        banjiId = int(request.POST.get('banjiId'))
        all_student_count = BanJi.objects.get(id = banjiId).students.count()-1
        teacher_id = user.id
        start_week = 0
        end_week = int(request.POST.get('endWeek', 18))
        interval = int(request.POST.get('interval', 1))

        queryList = []
        for i in range(start_week, end_week, interval):
            queryList.append(Event(
                position = position,
                has_signed_count = 0,
                all_student_count = all_student_count,
                started_time = (started_time + timedelta(days = 7 * i)).strftime("%Y-%m-%d %H:%M:%S"),
                closed_time = (closed_time + timedelta(days = 7 * i)).strftime("%Y-%m-%d %H:%M:%S"),
                banji_id = banjiId,
                teacher_id = user.id
            ))
        
        Event.objects.bulk_create(queryList)
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'success': False, 'errMsg': 'Permission denied'})


@csrf_exempt
def delete(request, eventId):
    Event.objects.filter(id = int(eventId)).delete()
    return JsonResponse({'success': True})

@login_required()
def detail(request, eventId):
    usergroup = 0 if 'usergroup' not in request.GET else request.GET['usergroup']
    return render(request, "sign_detail.html", {
        'eventId': eventId,
        'usergroup': usergroup,
    })
    # 以下内容为原始程序
    event = Event.objects.get(id = int(eventId))
    cursor = connection.cursor()
    sql = '\
        SELECT s.id, u.id_num, u.username, s.type_of, s.is_checked, s.created_time, \
               s.distance, s.studentposition, sl.cause, sl.path\
            FROM work_banji_students AS bj_stu\
                INNER JOIN auth_system_myuser AS u\
                ON u.id = bj_stu.myuser_id\
                INNER JOIN auth_system_myuser_groups AS u_group\
                ON u.id = u_group.myuser_id\
                LEFT JOIN sign_sign AS s\
                ON u.id = s.user_id and bj_stu.banji_id = (\
                    SELECT banji_id FROM sign_event WHERE id = %d and id = s.event_id\
                )\
                LEFT JOIN sign_leave AS sl\
                ON s.id = sl.sign_id\
                WHERE bj_stu.banji_id = %d and u_group.group_id=2\
                ORDER BY u.id_num' % ( int(eventId), event.banji_id )

    cursor.execute(sql)
    studentsList = list(map(lambda x: dict(zip(['id', 'id_num', 'username', 'type_of', 'is_checked', 'created_time', 'distance', 'studentposition', 'cause', 'path'], x)), cursor.fetchall()))
    return render(request, "sign_detail.html", {
        'data': studentsList,
        'eventId': eventId
    })

@login_required()
def student_index(request):
    userId = request.user.id
    # print(userId)
    cursor = connection.cursor()

    ongoingSQL = '\
        select e.id, tmp.name, e.position, e.started_time, e.closed_time\
        from sign_event AS e\
        join \
        (\
            select distinct bj_mid.banji_id, bj.name\
            from work_banji_students AS bj_mid\
            join work_banji AS bj\
            on bj_mid.banji_id = bj.id and bj_mid.myuser_id = %d\
        ) AS tmp\
        on e.banji_id = tmp.banji_id\
        where now() between e.started_time and e.closed_time\
    ' % userId
    cursor.execute(ongoingSQL)
    # print(ongoingSQL)
    onGoing = list(map(lambda x: dict(zip(['id', 'name', 'position', 'startTime', 'closedTime'], x)), cursor.fetchall()))
    onGoing = onGoing[0] if onGoing else []

    '''
    checkedSQL = '\
        select bj.name, s.created_time\
        from sign_sign AS s\
        join sign_event AS e\
        on s.event_id = e.id\
        join work_banji AS bj\
        on bj.id = e.banji_id\
        where user_id = %d\
    ' % userId
    cursor.execute(checkedSQL)
    checked = list(map(lambda x: dict(zip(['name', 'createdTime'], x)) ,cursor.fetchall()))
    '''
    
    banjis = BanJi.objects.filter(students=request.user)
    checked = []
    for banji in banjis:
        events = Event.objects.filter(banji=banji).order_by('started_time')
        for event in events:
            begin = event.started_time
            end = event.closed_time
            sign = Sign.objects.filter(event=event,user=request.user)
            if len(sign)>0:
                if sign[0].type_of==0:
                    status = '已签到'
                elif sign[0].type_of==1:
                    if sign[0].is_checked==1:
                        status = '假条已审核'
                    elif sign[0].is_checked==0:
                        status = '假条待审核'
            else:
                status = '未签到'
            checked.append({'id':event.id,'name':banji.name,'begin':begin,'end':end,'status':status})

    return render(request, "sign_student_index.html", {
        'onGoing': onGoing,
        'checked': checked,
    })


# 学生主动签到的动作
@login_required()
def checkout(request, eventId):
    eventId = int(eventId)
    try:
        ip =  request.META['HTTP_X_FORWARDED_FOR']
    except KeyError:
        ip = request.META['REMOTE_ADDR']

    if Sign.objects.filter(event_id = eventId, user_id = request.user.id):
        return JsonResponse({'success': False, 'errMsg': '你已经签到过了，无需再次签到'})

    #if Record.objects.filter(event_id = eventId, address = ip):
    #    return JsonResponse({'success': False, 'errMsg': '签到无效，同一设备不可重复签到'})

    try:
        event = Event.objects.get(id = eventId)
        if not event.started_time <= datetime.now() <= event.closed_time:
            return JsonResponse({'success': False, 'errMsg': '签到失败，不在允许的时间段'})
        event.has_signed_count = event.has_signed_count + 1
        event.save()

        Sign.objects.create(
            event_id = eventId,
            user_id = request.user.id,
            type_of = 0,
            is_checked = 1,
            distance = request.POST['distance'],
            studentposition = request.POST['studentposition']
        )

        Record.objects.create(
            event_id = eventId,
            address = ip
        )
    except:
        logger_request.exception("签到信息保存遇到问题，用户提交数据如下：{}".format(request.POST.dict()))

    return JsonResponse({'success': True})



#老师手动输入学号帮助学生签到
@csrf_exempt
def supplement(request, eventId):
    eventId = int(eventId)
    studentId = request.POST.get('studentId')
    
    try:
        userId = MyUser.objects.get(id_num = studentId).id        
    except:
        return JsonResponse({'success': False, 'code': 404, 'errMsg': 'can not find user by studentId'})

    try:
        sign = Sign.objects.get(event_id=eventId,user_id=userId)
    except ObjectDoesNotExist:
        Sign.objects.create(
            event_id = eventId,
            user_id = userId,
            type_of = 0,
            is_checked = 1
        )

        event = Event.objects.get(id = eventId)
        event.has_signed_count = event.has_signed_count + 1
        event.save()

    return JsonResponse({'success': True})

@csrf_exempt
def leave(request, eventId):
    userId = request.user.id
    eventId = int(eventId)

    if Sign.objects.filter(event_id = eventId, user_id = userId):
        return JsonResponse({'success': False, 'errMsg': '请勿重复签到'})

    fileObj = request.FILES.get('leaveAsk')
    #检测文件后缀名和 MINE 格式
    #暂时还不知道 怎么判断上传文件的 MINE 类型，目前只根据后缀检查一下
    if os.path.splitext(fileObj.name)[1].lower() not in ('.jpg', '.jpeg', '.png'):
        return JsonResponse({'success': False, 'state': 0, 'msg': 'upload file can only be .jpg .jpeg .png'})

    date = datetime.now().strftime('%Y/%m/%d/').split('/')
    pathdir = os.path.join(STATIC_ROOT, 'pic', date[0], date[1], date[2])
    # print(pathdir)
    if not os.path.exists(pathdir):
        os.makedirs(pathdir)
    
    fileName = str(uuid.uuid1())
    f = open(os.path.join(pathdir, fileName), 'wb')
    for chunk in fileObj.chunks():
        f.write(chunk)
    f.close()

    signObj = Sign(event_id = eventId, user_id = userId, type_of = 1, is_checked = 0)
    signObj.save()

    Leave.objects.create(
        sign_id = signObj.id,
        path = os.path.join('pic', date[0], date[1], date[2], fileName),
        cause = request.POST.get('cause')
    )

    return JsonResponse({'success': True, 'state': 1, 'path': os.path.splitext(fileObj.name)})


@csrf_exempt
def accept (request, signId):
    sign = Sign.objects.get(id = signId)
    sign.is_checked = 1

    event = Event.objects.get(id = sign.event_id)
    event.has_signed_count = event.has_signed_count + 1
    
    event.save()
    sign.save()

    # cursor = connection.cursor()
    # sql = 'SELECT path FROM sign_leave WHERE sign_id = %d' % int(signId)
    # cursor.execute(sql)
    # lPath = cursor.fetchall()
    # os.remove(STATIC_ROOT + '/' + lPath[0][0])

    # sql = 'DELETE FROM sign_leave WHERE sign_id = %d' % int(signId)
    # cursor.execute(sql)

    return JsonResponse({'success': True})


@csrf_exempt
def decline (request, signId):

    cursor = connection.cursor()
    #sql = 'DELETE FROM sign_sign WHERE id = %d' % int(signId)
    #cursor.execute(sql)
    
    sql = 'SELECT path FROM sign_leave WHERE sign_id = %d' % int(signId)
    cursor.execute(sql)
    lPath = cursor.fetchall()
    os.remove(STATIC_ROOT + '/' + lPath[0][0])
    #os.remove(BASE_DIR + '/static/' + lPath[0][0])

    id = int(signId)
    Sign.objects.filter(pk = id).delete()

    sql = 'DELETE FROM sign_leave WHERE sign_id = %d' % int(signId)
    cursor.execute(sql)

    return JsonResponse({'success': True})

@login_required()
def get_sign_list(request,eventId):
    event = Event.objects.get(id = int(eventId))
    cursor = connection.cursor()
    sql = '\
        SELECT s.id, u.id_num, u.username, s.type_of, s.is_checked, s.created_time, \
               s.distance, s.studentposition, sl.cause, sl.path\
            FROM work_banji_students AS bj_stu\
                INNER JOIN auth_system_myuser AS u\
                ON u.id = bj_stu.myuser_id\
                INNER JOIN auth_system_myuser_groups AS u_group\
                ON u.id = u_group.myuser_id\
                LEFT JOIN sign_sign AS s\
                ON u.id = s.user_id and bj_stu.banji_id = (\
                    SELECT banji_id FROM sign_event WHERE id = %d and id = s.event_id\
                )\
                LEFT JOIN sign_leave AS sl\
                ON s.id = sl.sign_id\
                WHERE bj_stu.banji_id = %d and u_group.group_id=2\
                ' % ( int(eventId), event.banji_id )
    if 'search' in request.GET.dict():
        sql += ' and (u.id_num like "%' + request.GET['search'] \
             + '%" or u.username like "%' + request.GET['search'] + '%")'
    cursor.execute(sql)
    studentsList = list(map(lambda x: dict(zip(['id', 'id_num', 'username', 'type_of', 'is_checked', 'created_time', 'distance', 'studentposition', 'cause', 'path'], x)), cursor.fetchall()))
    offset = int(request.GET['offset'])
    limit = int(request.GET['limit'])
    try:
        sort = request.GET['sort']
    except MultiValueDictKeyError:
        sort = 'id_num'
    if request.GET['order'] == 'desc':
        reverse = True
    else:
        reverse = False
    for dicts in studentsList:
        if dicts['created_time'] is not None:
            dicts['created_time'] = datetime.strftime(dicts['created_time'],'%Y年%m月%d日 %H:%M:%S')
        if dicts['type_of'] == 1:
            if dicts['is_checked'] == 1:
                dicts['status'] = '假条已审核'
            elif dicts['is_checked'] == 0:
                dicts['status'] = '假条待审核'
        elif dicts['type_of'] == 0:
            dicts['status'] = '正常签到'
            # if dicts['studentposition'] == 'null':
            #     dicts['studentposition'] = '未知'
            # if dicts['distance'] is None:
            #     dicts['distance'] = '未知'
        else:
            dicts['status'] = '未签到'
    try:
        usergroup = request.GET['usergroup']
        if usergroup == '1':
            studentsList = [stu for stu in studentsList if stu['status']=='正常签到']
        elif usergroup == '2':
            studentsList = [stu for stu in studentsList if stu['status']=='未签到']
        elif usergroup == '3':
            studentsList = [stu for stu in studentsList if stu['status']=='假条已审核']
        elif usergroup == '4':
            studentsList = [stu for stu in studentsList if stu['status']=='假条待审核']

    except MultiValueDictKeyError:
        pass
    if sort=="created_time":
        studentsList.sort(key=lambda a:str(a.get(sort)), reverse=reverse)
    elif sort=="distance":
        studentsList.sort(key=lambda a:0 if a.get(sort) is None else a.get(sort), reverse=reverse)
    else:
        studentsList.sort(key=lambda a:a.get(sort), reverse=reverse)
    json_data = {}
    json_data['total']=len(studentsList)
    json_data['rows']=studentsList[offset:offset + limit]
    return JsonResponse(json_data)

@login_required()
def get_event_config(request):
    """
    获取签到事件的信息
    """
    if request.user.isTeacher() and 'id' in request.GET.dict():
        event = Event.objects.get(pk=request.GET['id'])
        starttime = datetime.strftime(event.started_time,'%Y-%m-%d %H:%M')
        endtime = datetime.strftime(event.closed_time,'%Y-%m-%d %H:%M')
        return JsonResponse({"id":event.pk,"starttime":starttime,"endtime":endtime})
    else:
        return JsonResponse(dict())

@login_required()
def save_event_config(request):
    if request.user.isTeacher() and 'id' in request.POST.dict():
        event = Event.objects.get(pk=request.POST['id'])
        if request.user == event.teacher or request.user.is_admin:
            temp = request.POST.dict()
            event.started_time = request.POST['starttime']
            event.closed_time = request.POST['endtime']
            event.save()
            return JsonResponse({'result':'ok'})
    return JsonResponse(dict())

def setAddress (request, signId, userId, address):
    pass
