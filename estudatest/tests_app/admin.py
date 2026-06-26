from django.contrib import admin
from .models import Test, Question

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'category', 'updated_at']

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'test', 'order', 'question_type']
