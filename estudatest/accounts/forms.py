from django import forms
from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form__input',
            'placeholder': 'Usuário ou e-mail',
            'autocomplete': 'username',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form__input',
            'placeholder': '••••••••',
            'autocomplete': 'current-password',
        })
    username = forms.CharField(label='Usuário')
    password = forms.CharField(label='Senha', widget=forms.PasswordInput)
