from django import forms
from .models import Category


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Nome da categoria', 'autofocus': True}),
        }
        labels = {'name': 'Nome'}
