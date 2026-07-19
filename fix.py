from auth_system.models import MyUser
from django.contrib import auth
from django.db.models import Q

# 2025年3月7日，修复弱密码问题
def fixWeakPassword():
    users = MyUser.objects.filter(Q(school_short__isnull=True) | Q(school_short='')).all()
    print(len(users))
    count = 21000
    for user in users[21000:]:
        count += 1
        if auth.authenticate(username=user.email, password=user.id_num):
            user.set_password(user.id_num + '@Njupt')
            user.save()
            print(count,"Account:",user.id_num,"fixed.")
        else:
            print(count,"Don't need fix.")

fixWeakPassword()
