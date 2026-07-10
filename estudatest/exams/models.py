from django.db import models
from django.contrib.auth.models import User
from categories.models import Category
from django.core.validators import MaxLengthValidator
from django.core.exceptions import ValidationError
from polymorphic.models import PolymorphicModel
import unicodedata
import re

class Exam(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exams')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='exams')
    name = models.CharField(max_length=30, unique=True)
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


 
class Question(PolymorphicModel):
    class Types(models.TextChoices):
        MULTIPLE_CHOICE = 'multiple_choice', 'Múltipla escolha'
        MULTI_ANSWER = 'multi_answer', 'Resposta múltipla'
        TRUE_FALSE = 'true_false', 'Verdadeiro ou falso'
        WRITTEN = 'written', 'Resposta escrita'
        ORDERING = 'ordering', 'Ordenar elementos'
        MATCHING = 'matching', 'Relacionar colunas'
        FLASHCARD = 'flashcard', 'Flashcard'

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='questions')
    order = models.PositiveIntegerField(default=0)
    question_type = models.CharField(max_length=20, choices=Types.choices, editable=False)
    statement = models.TextField(validators=[MaxLengthValidator(1000)], blank=False)
    explanation = models.TextField(validators=[MaxLengthValidator(1000)], blank=False)

    is_automatable = True
 
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

    def check_answer(self, given_answer):
        """Recebe a resposta dada e retorna bool."""
        raise NotImplementedError('Implementado pelas subclasses concretas.')
 
    def correct_answer_display(self):
        """Representação legível da resposta correta, para telas de revisão."""
        raise NotImplementedError('Implementado pelas subclasses concretas.')

# Múltipla escolha / Resposta múltipla

class ChoiceQuestionMixin(models.Model):
    class Meta:
        abstract = True
 
    def check_answer(self, given_answer):
        if not isinstance(given_answer, (list, tuple, set)):
            return False
        given_ids = {str(x) for x in given_answer}
        options_list = list(self.options.all())
        correct_ids = {str(o.pk) for o in options_list if o.is_correct}
        return given_ids == correct_ids

    def correct_answer_display(self):
        options_list = list(self.options.all())
        return ', '.join(o.text for o in options_list if o.is_correct)
 
class QuestionOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.text

class MultipleChoiceQuestion(ChoiceQuestionMixin, Question):
    def save(self, *args, **kwargs):
        self.question_type = Question.Types.MULTIPLE_CHOICE
        super().save(*args, **kwargs)

class MultiAnswerQuestion(ChoiceQuestionMixin, Question):
    def save(self, *args, **kwargs):
        self.question_type = Question.Types.MULTI_ANSWER
        super().save(*args, **kwargs)


# Verdadeiro ou falso

class TrueFalseQuestion(Question):
    correct_answer = models.BooleanField()
 
    def save(self, *args, **kwargs):
        self.question_type = Question.Types.TRUE_FALSE
        super().save(*args, **kwargs)
 
    def check_answer(self, given_answer):
        if isinstance(given_answer, str):
            given_answer = given_answer.strip().lower() in ('true', '1', 'verdadeiro')
        return bool(given_answer) == self.correct_answer
 
    def correct_answer_display(self):
        return 'Verdadeiro' if self.correct_answer else 'Falso'


# Resposta escrita

class WrittenQuestion(Question):
    expected_answer = models.CharField(max_length=255)
    case_sensitive = models.BooleanField(default=False)
    accepted_alternatives = models.JSONField(default=list, blank=True)
 
    def save(self, *args, **kwargs):
        self.question_type = Question.Types.WRITTEN
        super().save(*args, **kwargs)
 
    def _normalize(self, value):
        value = (value or '').strip()
        if not self.case_sensitive:
            value = value.lower()
        
        # Se quiser a limpeza profunda que tinha no arquivo antigo:
        value = unicodedata.normalize('NFD', value)
        value = ''.join(c for c in value if unicodedata.category(c) != 'Mn') # Remove acentos
        value = re.sub(r'[^\w\s]', '', value) # Remove pontuação
        value = re.sub(r'\s+', ' ', value).strip() # Remove espaços extras
        
        return value
 
    def check_answer(self, given_answer):
        candidates = [self.expected_answer, *self.accepted_alternatives]
        normalized_candidates = {self._normalize(c) for c in candidates}
        return self._normalize(given_answer) in normalized_candidates
 
    def correct_answer_display(self):
        return self.expected_answer


# Ordenar elementos

class OrderingQuestion(Question):
    def save(self, *args, **kwargs):
        self.question_type = Question.Types.ORDERING
        super().save(*args, **kwargs)
 
    def check_answer(self, given_answer):
        if not isinstance(given_answer, (list, tuple)):
            return False
        
        # Otimizado para usar cache se houver prefetch_related('items')
        items_list = sorted(list(self.items.all()), key=lambda x: x.position)
        correct_order = [item.id for item in items_list]
        
        try:
            given_ids = [int(x) for x in given_answer]
        except (TypeError, ValueError):
            return False
        return given_ids == correct_order
 
    def correct_answer_display(self):
        items_list = sorted(list(self.items.all()), key=lambda x: x.position)
        return ' → '.join(item.text for item in items_list)

class OrderingItem(models.Model):
    question = models.ForeignKey(OrderingQuestion, on_delete=models.CASCADE, related_name='items')
    text = models.CharField(max_length=500)
    position = models.PositiveIntegerField()
 
    class Meta:
        ordering = ['position']
 
    def __str__(self):
        return self.text


# Relacionar colunas

class MatchingQuestion(Question):
    def save(self, *args, **kwargs):
        self.question_type = Question.Types.MATCHING
        super().save(*args, **kwargs)
 
    def check_answer(self, given_answer):
        # Aceita dois formatos: dict {pair_id: right} (antigo) ou
        # lista de rights em ordem da coluna esquerda (enviado pelo JS).
        pairs_list = list(self.pairs.all())
        if isinstance(given_answer, dict):
            pairs = {str(p.pk): p.right for p in pairs_list}
            if set(given_answer.keys()) != set(pairs.keys()):
                return False
            return all(str(given_answer[k]) == str(pairs[k]) for k in pairs)

        if isinstance(given_answer, (list, tuple)):
            rights_submitted = [str(x) for x in given_answer]
            correct_rights = [str(p.right) for p in sorted(pairs_list, key=lambda x: x.order)]
            return rights_submitted == correct_rights

        return False
 
    def correct_answer_display(self):
        return '; '.join(f'{p.left} — {p.right}' for p in self.pairs.all())

class MatchingPair(models.Model):
    question = models.ForeignKey(MatchingQuestion, on_delete=models.CASCADE, related_name='pairs')
    left = models.CharField(max_length=500)
    right = models.CharField(max_length=500)
    order = models.PositiveIntegerField(default=0)
 
    class Meta:
        ordering = ['order']
 
    def __str__(self):
        return f'{self.left} — {self.right}'


# Flashcard

class FlashcardQuestion(Question):
    front = models.TextField(validators=[MaxLengthValidator(1000)], blank=False)
    back = models.TextField(validators=[MaxLengthValidator(1000)], blank=False)

    is_automatable = False
 
    def save(self, *args, **kwargs):
        self.question_type = Question.Types.FLASHCARD
        super().save(*args, **kwargs)
 
    def check_answer(self, given_answer):
        return False
 
    def correct_answer_display(self):
        return self.back