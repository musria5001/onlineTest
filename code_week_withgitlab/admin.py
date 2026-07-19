from django.contrib import admin
from .models import ProblemCategory,CodeWeekClass,ShejiProblem,CodeWeekClassGroup,CodeWeekClassStudent

admin.site.register(ProblemCategory)
admin.site.register(CodeWeekClass)
admin.site.register(ShejiProblem)
admin.site.register(CodeWeekClassGroup)
admin.site.register(CodeWeekClassStudent)
# Register your models here.
