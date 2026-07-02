from django.contrib import admin
from .models import Exam, Question

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'category', 'updated_at']

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'exam', 'order', 'question_type']
