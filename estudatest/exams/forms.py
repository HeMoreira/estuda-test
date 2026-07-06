from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.db import models

from .models import (
    Exam,
    Question,
    QuestionOption,
    MultipleChoiceQuestion,
    MultiAnswerQuestion,
    TrueFalseQuestion,
    WrittenQuestion,
    OrderingQuestion, OrderingItem,
    MatchingQuestion, MatchingPair,
    FlashcardQuestion,
)


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['name', 'category']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form__input', 'placeholder': 'Nome da prova'}),
            'category': forms.Select(attrs={'class': 'form__select'}),
        }
        labels = {
            'name': 'Nome da Prova',
            'category': 'Categoria',
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'category' in self.fields:
            self.fields['category'].queryset = self.fields['category'].queryset.filter(
                models.Q(user=user)
            ).exclude(name='~ sem categoria')


class QuestionTypeForm(forms.Form):
    question_type = forms.ChoiceField(choices=Question.Types.choices, label='Tipo de questão')


COMMON_WIDGETS = {
    'statement': forms.Textarea(attrs={
        'class': 'form__textarea', 'rows': 4,
        'placeholder': 'Digite o enunciado da questão...',
    }),
    'explanation': forms.Textarea(attrs={
        'class': 'form__textarea', 'rows': 3,
        'placeholder': 'Explique por que a resposta é correta...',
    }),
}

COMMON_LABELS = {
    'statement': 'Enunciado',
    'explanation': 'Explicação da resposta',
}


class BaseQuestionForm(forms.ModelForm):
    statement = forms.CharField(widget=COMMON_WIDGETS['statement'], label=COMMON_LABELS['statement'], max_length=1000, required=True)
    explanation = forms.CharField(widget=COMMON_WIDGETS['explanation'], label=COMMON_LABELS['explanation'], max_length=1000, required=True)

    class Meta:
        fields = ['statement', 'explanation']


class MultipleChoiceQuestionForm(BaseQuestionForm):
    class Meta(BaseQuestionForm.Meta):
        model = MultipleChoiceQuestion


class MultiAnswerQuestionForm(BaseQuestionForm):
    class Meta(BaseQuestionForm.Meta):
        model = MultiAnswerQuestion


class TrueFalseQuestionForm(BaseQuestionForm):
    class Meta(BaseQuestionForm.Meta):
        model = TrueFalseQuestion
        fields = BaseQuestionForm.Meta.fields + ['correct_answer']
        widgets = {
            **COMMON_WIDGETS,
            'correct_answer': forms.RadioSelect(choices=((True, 'Verdadeiro'), (False, 'Falso'))),
        }
        labels = {**COMMON_LABELS, 'correct_answer': 'Resposta correta'}


class WrittenQuestionForm(BaseQuestionForm):
    accepted_alternatives_raw = forms.CharField(
        required=False,
        label='Respostas alternativas aceitas (uma por linha)',
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form__textarea'}),
    )

    class Meta(BaseQuestionForm.Meta):
        model = WrittenQuestion
        fields = BaseQuestionForm.Meta.fields + ['expected_answer', 'case_sensitive']
        labels = {
            **COMMON_LABELS,
            'expected_answer': 'Resposta esperada',
            'case_sensitive': 'Diferenciar maiúsculas/minúsculas',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['accepted_alternatives_raw'].initial = '\n'.join(
                self.instance.accepted_alternatives
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw = self.cleaned_data.get('accepted_alternatives_raw', '')
        instance.accepted_alternatives = [line.strip() for line in raw.splitlines() if line.strip()]
        if commit:
            instance.save()
        return instance


class FlashcardQuestionForm(BaseQuestionForm):
    class Meta(BaseQuestionForm.Meta):
        model = FlashcardQuestion
        fields = BaseQuestionForm.Meta.fields + ['front', 'back']
        widgets = {
            **COMMON_WIDGETS,
            'front': forms.Textarea(attrs={'rows': 3, 'class': 'form__textarea'}),
            'back': forms.Textarea(attrs={'rows': 3, 'class': 'form__textarea'}),
        }
        labels = {**COMMON_LABELS, 'front': 'Frente', 'back': 'Verso'}


class OrderingQuestionForm(BaseQuestionForm):
    class Meta(BaseQuestionForm.Meta):
        model = OrderingQuestion


class MatchingQuestionForm(BaseQuestionForm):
    class Meta(BaseQuestionForm.Meta):
        model = MatchingQuestion


# ==========================================================================
# Formsets para os dados relacionados (opções, itens, pares)
# ==========================================================================

OPTION_WIDGETS = {'text': forms.TextInput(attrs={'class': 'form__input', 'placeholder': 'Texto da opção'})}

MultipleChoiceOptionFormSet = inlineformset_factory(
    MultipleChoiceQuestion, QuestionOption,
    fields=['text', 'is_correct', 'order'],
    extra=2, can_delete=True, widgets=OPTION_WIDGETS,
)

MultiAnswerOptionFormSet = inlineformset_factory(
    MultiAnswerQuestion, QuestionOption,
    fields=['text', 'is_correct', 'order'],
    extra=2, can_delete=True, widgets=OPTION_WIDGETS,
)

OrderingItemFormSet = inlineformset_factory(
    OrderingQuestion, OrderingItem,
    fields=['text', 'position'],
    extra=2, can_delete=True,
    widgets={'text': forms.TextInput(attrs={'class': 'form__input', 'placeholder': 'Elemento'})},
)

MatchingPairFormSet = inlineformset_factory(
    MatchingQuestion, MatchingPair,
    fields=['left', 'right', 'order'],
    extra=2, can_delete=True,
    widgets={
        'left': forms.TextInput(attrs={'class': 'form__input', 'placeholder': 'Coluna A'}),
        'right': forms.TextInput(attrs={'class': 'form__input', 'placeholder': 'Coluna B'}),
    },
)

QUESTION_TYPE_REGISTRY = {
    Question.Types.MULTIPLE_CHOICE: (MultipleChoiceQuestionForm, MultipleChoiceOptionFormSet),
    Question.Types.MULTI_ANSWER: (MultiAnswerQuestionForm, MultiAnswerOptionFormSet),
    Question.Types.TRUE_FALSE: (TrueFalseQuestionForm, None),
    Question.Types.WRITTEN: (WrittenQuestionForm, None),
    Question.Types.ORDERING: (OrderingQuestionForm, OrderingItemFormSet),
    Question.Types.MATCHING: (MatchingQuestionForm, MatchingPairFormSet),
    Question.Types.FLASHCARD: (FlashcardQuestionForm, None),
}