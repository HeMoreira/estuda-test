from django.contrib import admin
from .models import Attempt, AnswerRecord

@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'exam', 'started_at', 'score']

@admin.register(AnswerRecord)
class AnswerRecordAdmin(admin.ModelAdmin):
    list_display = ['attempt', 'question', 'is_correct']
