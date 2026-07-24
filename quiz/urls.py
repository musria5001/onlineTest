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
    url(r'^teacher/kp/$', views.teacher_kp_manage, name='quiz_teacher_kp_manage'),
    url(r'^teacher/kp/(?P<kp2_id>\d+)/$', views.teacher_kp_questions, name='quiz_teacher_kp_questions'),
]
