from django.db import models
from django.contrib.auth.models import User
from categories.models import Category


class Test(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tests')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='tests')
    name = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category__name', 'name']
        verbose_name = 'Prova'
        verbose_name_plural = 'Provas'

    def __str__(self):
        return self.name

    def question_count(self):
        return self.questions.count()


QUESTION_TYPES = [
    ('multiple_choice', 'Múltipla escolha'),
    ('multi_answer', 'Resposta múltipla'),
    ('true_false', 'Verdadeiro ou falso'),
    ('written', 'Resposta escrita'),
    ('ordering', 'Ordenar elementos'),
    ('matching', 'Relacionar colunas'),
    ('flashcard', 'Flashcard'),
]


class Question(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='questions')
    order = models.PositiveIntegerField(default=0)
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    statement = models.TextField()
    data = models.JSONField(default=dict)
    explanation = models.TextField()

    class Meta:
        ordering = ['order']
        verbose_name = 'Questão'
        verbose_name_plural = 'Questões'

    def __str__(self):
        return f"{self.get_question_type_display()} — {self.statement[:60]}"

    def statement_preview(self):
        lines = self.statement.strip().split('\n')
        preview = '\n'.join(lines[:2])
        if len(lines) > 2 or len(preview) > 120:
            return preview[:120] + '...'
        return preview
