from django import forms
from django.db import models
from .models import Exam, Question


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['name', 'category']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form__input', 'placeholder': 'Nome da prova'}),
            'category': forms.Select(attrs={'class': 'form__select'}),
        }
        labels = {'name': 'Nome da Prova', 'category': 'Categoria'}

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'category' in self.fields:
            self.fields['category'].queryset = self.fields['category'].queryset.filter(
                models.Q(user=user)
            ).exclude(name='~ sem categoria')


class QuestionTypeForm(forms.Form):
    question_type = forms.ChoiceField(choices=Question.Types.choices, label='Tipo de questão')