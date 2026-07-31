from django.conf.urls import url
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    url(r'^teacher_sign$', RedirectView.as_view(url='/quiz/teacher/', permanent=False), name='sign.teacher.index'),
    url(r'^create$', views.create, name='sign.create'),
    url(r'^detail/(\d+)$', views.detail, name='sign.detail'),
    url(r'^delete/(\d+)$', views.delete, name='sign.delete'),    
    url(r'^supplement/(\d+)$', views.supplement, name='sign.supplement'),  
    url(r'^accept/(\d+)$', views.accept, name='sign.accept'),
    url(r'^decline/(\d+)$', views.decline, name='sign.decline'),  

    url(r'^student_sign$', RedirectView.as_view(url='/quiz/', permanent=False), name='sign.student.index'),
    url(r'^checkout/(\d+)$', views.checkout, name='sign.checkout'),
    url(r'^leave/(\d+)$', views.leave, name='sign.leave'),
    url(r'^get_sign_list/(\d+)$', views.get_sign_list, name='sign.get_sign_list'),

    url(r'^get-event-config/$', views.get_event_config, name='get_event_config'),
    url(r'^save-event-config/$', views.save_event_config, name='save_event_config'),

]
