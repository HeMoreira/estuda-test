"""
Testes unitários para exams/forms.py
 
Cobre:
- ExamForm: filtragem do queryset de categoria por usuário e exclusão
  da categoria padrão '~ sem categoria' das opções visíveis
- QuestionTypeForm: validação de escolhas válidas/ inválidas
"""
from django.contrib.auth.models import User
from django.test import TestCase
 
from categories.models import Category
from exams.forms import ExamForm, QuestionTypeForm
from exams.models import Question
 
 
class ExamFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='formuser', password='pass12345')
        self.other_user = User.objects.create_user(username='outro', password='pass12345')
 
    def test_category_queryset_limited_to_user(self):
        own_cat = Category.objects.create(user=self.user, name='Minha categoria')
        Category.objects.create(user=self.other_user, name='Categoria de outro usuário')
 
        form = ExamForm(self.user)
        queryset_ids = set(form.fields['category'].queryset.values_list('pk', flat=True))
 
        self.assertIn(own_cat.pk, queryset_ids)
        self.assertEqual(len(queryset_ids), 1)
 
    def test_default_category_excluded_from_choices(self):
        Category.objects.create(user=self.user, name='~ sem categoria')
        visible_cat = Category.objects.create(user=self.user, name='Visível')
 
        form = ExamForm(self.user)
        names = set(form.fields['category'].queryset.values_list('name', flat=True))
 
        self.assertIn('Visível', names)
        self.assertNotIn('~ sem categoria', names)
 
    def test_valid_form_with_name_only(self):
        form = ExamForm(self.user, data={'name': 'Prova Teste', 'category': ''})
        self.assertTrue(form.is_valid(), form.errors)
 
    def test_invalid_form_without_name(self):
        form = ExamForm(self.user, data={'name': '', 'category': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
 
 
class QuestionTypeFormTests(TestCase):
    def test_valid_choice(self):
        form = QuestionTypeForm(data={'question_type': Question.Types.FLASHCARD})
        self.assertTrue(form.is_valid())
 
    def test_invalid_choice_rejected(self):
        form = QuestionTypeForm(data={'question_type': 'nao_existe'})
        self.assertFalse(form.is_valid())
 
    def test_missing_choice_rejected(self):
        form = QuestionTypeForm(data={})
        self.assertFalse(form.is_valid())
