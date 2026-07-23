from django.db import models

from auth_system.models import MyUser
from judge.models import ChoiceProblem, DuchengProblem, KnowledgePoint2
from work.models import BanJi


CHOICE = 'choice'
DUCHENG = 'ducheng'
QUESTION_TYPES = ((CHOICE, '选择题'), (DUCHENG, '填空题'))


class QuizAssignment(models.Model):
    """教师布置的知识点作业"""
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=100, verbose_name='作业标题')
    teacher = models.ForeignKey(MyUser, verbose_name='布置教师')
    banji = models.ForeignKey(BanJi, verbose_name='目标班级')
    kp2 = models.ForeignKey(KnowledgePoint2, verbose_name='指定知识点')
    choice_count = models.IntegerField(default=0, verbose_name='选择题数量')
    ducheng_count = models.IntegerField(default=0, verbose_name='填空题数量')
    question_count = models.IntegerField(default=5, verbose_name='要求答题数')
    deadline = models.DateTimeField(null=True, blank=True, verbose_name='截止时间')
    created_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'quiz_assignment'
        verbose_name = '知识点作业'
        verbose_name_plural = '知识点作业'
        ordering = ['-created_time']

    def __str__(self):
        return self.title


class AnswerRecord(models.Model):
    """学生单次答题记录。存在即表示已答过，不可重复答同一题。"""
    CHOICE = 'choice'
    DUCHENG = 'ducheng'

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(MyUser, verbose_name='学生')
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPES, default=CHOICE, verbose_name='题型')
    choice_question = models.ForeignKey(ChoiceProblem, verbose_name='选择题', null=True, blank=True, on_delete=models.CASCADE)
    ducheng_question = models.ForeignKey(DuchengProblem, verbose_name='填空题', null=True, blank=True, on_delete=models.CASCADE)
    kp2 = models.ForeignKey(KnowledgePoint2, verbose_name='所属二级知识点')
    banji = models.ForeignKey(BanJi, verbose_name='所属班级', null=True, blank=True)
    assignment = models.ForeignKey(QuizAssignment, verbose_name='所属作业', null=True, blank=True, on_delete=models.SET_NULL)
    is_correct = models.BooleanField(verbose_name='是否正确', default=False)
    points = models.FloatField(verbose_name='获得积分', default=0)
    round_num = models.IntegerField(verbose_name='第几轮', default=1)
    student_answer = models.CharField(max_length=500, verbose_name='学生答案', blank=True, default='')
    created_time = models.DateTimeField(auto_now_add=True, verbose_name='答题时间')

    class Meta:
        db_table = 'quiz_answer_record'
        verbose_name = '答题记录'
        verbose_name_plural = '答题记录'
        ordering = ['-created_time']

    def __str__(self):
        return '%s - %s' % (self.user.username, self.get_question_title()[:20])

    def get_question_title(self):
        if self.question_type == self.CHOICE and self.choice_question:
            return self.choice_question.title
        if self.question_type == self.DUCHENG and self.ducheng_question:
            return self.ducheng_question.title
        return '(已删除)'
