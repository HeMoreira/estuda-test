from django import forms
from .models import Test, Question, QUESTION_TYPES
from categories.models import Category


class TestForm(forms.ModelForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(user=user)
        self.fields['category'].empty_label = '— Sem categoria —'
        self.fields['name'].widget.attrs.update({'class': 'form__input', 'placeholder': 'Nome da prova'})
        self.fields['category'].widget.attrs.update({'class': 'form__select'})

    class Meta:
        model = Test
        fields = ['name', 'category']
        labels = {'name': 'Nome da prova', 'category': 'Categoria'}


class QuestionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['statement'].widget.attrs.update({
            'class': 'form__textarea', 'rows': 4,
            'placeholder': 'Digite o enunciado da questão...',
        })
        self.fields['explanation'].widget.attrs.update({
            'class': 'form__textarea', 'rows': 3,
            'placeholder': 'Explique por que a resposta é correta...',
        })

    class Meta:
        model = Question
        fields = ['question_type', 'statement', 'explanation']
        labels = {
            'question_type': 'Tipo de questão',
            'statement': 'Enunciado',
            'explanation': 'Explicação da resposta',
        }
