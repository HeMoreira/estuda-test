from django.db import models
from django.contrib.auth.models import User
from tests_app.models import Test, Question


class Attempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attempts')
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)  # 0.0 to 1.0

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Tentativa'
        verbose_name_plural = 'Tentativas'

    def __str__(self):
        return f"{self.user.username} — {self.test.name} ({self.started_at:%d/%m/%Y})"

    def score_percent(self):
        if self.score is None:
            return None
        return round(self.score * 100)


class AnswerRecord(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answer_records')
    given_answer = models.JSONField()
    is_correct = models.BooleanField()

    class Meta:
        verbose_name = 'Resposta'
        verbose_name_plural = 'Respostas'
