from django.conf.urls import url

from . import views

urlpatterns = [
    # 学生端
    url(r'^$', views.kp_tree, name='quiz_kp_tree'),
    url(r'^kp2/(?P<kp2_id>\d+)/$', views.answer_question, name='quiz_answer'),
    url(r'^kp2/(?P<kp2_id>\d+)/submit/$', views.submit_answer, name='quiz_submit'),
    url(r'^points/$', views.my_points, name='quiz_points'),
    url(r'^leaderboard/$', views.leaderboard, name='quiz_leaderboard'),
    # 教师端
    url(r'^teacher/$', views.teacher_dashboard, name='quiz_teacher_dashboard'),
    url(r'^teacher/class/(?P<banji_id>\d+)/$', views.teacher_class_progress, name='quiz_teacher_class'),
    url(r'^teacher/class/(?P<banji_id>\d+)/student/(?P<user_id>\d+)/$', views.teacher_student_records, name='quiz_teacher_student'),
    url(r'^teacher/assignment/create/$', views.teacher_assignment_create, name='quiz_teacher_assignment_create'),
    url(r'^teacher/assignment/list/$', views.teacher_assignment_list, name='quiz_teacher_assignment_list'),
    url(r'^teacher/assignment/delete/(?P<assignment_id>\d+)/$', views.teacher_assignment_delete, name='quiz_teacher_assignment_delete'),
    url(r'^student/assignments/$', views.student_assignments, name='quiz_student_assignments'),
    url(r'^teacher/kp/$', views.teacher_kp_manage, name='quiz_teacher_kp_manage'),
    url(r'^teacher/kp/(?P<kp2_id>\d+)/$', views.teacher_kp_questions, name='quiz_teacher_kp_questions'),
    url(r'^teacher/kp/(?P<kp2_id>\d+)/add/$', views.teacher_add_question, name='quiz_teacher_add_question'),
    url(r'^teacher/kp/(?P<kp2_id>\d+)/link/$', views.teacher_link_questions, name='quiz_teacher_link_questions'),
    url(r'^teacher/ajax-kp1/$', views.teacher_ajax_kp1s, name='quiz_teacher_ajax_kp1s'),
    url(r'^teacher/ajax-kp2/$', views.teacher_ajax_kp2s, name='quiz_teacher_ajax_kp2s'),
    url(r'^teacher/search-questions/$', views.teacher_search_questions, name='quiz_teacher_search_questions'),
    url(r'^teacher/question/(?P<question_id>\d+)/delete/$', views.teacher_delete_question, name='quiz_teacher_delete_question'),
]
