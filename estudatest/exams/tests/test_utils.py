"""
Testes unitários para exams/utils.py

Cobre apenas a responsabilidade própria deste módulo: categoria padrão,
orquestração da validação comum + delegação por tipo, delegação de
serialização de edição, e achatamento de ValidationError.
As regras específicas de cada tipo de questão são testadas em
test_question_types.py (question_types/*).
"""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from categories.models import Category
from exams.forms import ExamForm
from exams.models import Exam, Question, TrueFalseQuestion
from exams.utils import (
    save_exam_with_default_category_if_needed,
    validate_question_payload,
    build_question_edit_data,
    flatten_validation_errors,
)
from .test_support import make_querydict


class _FakeRequest:
    """Stub simples para simular request.user nas funções que só usam esse atributo."""
    def __init__(self, user):
        self.user = user


class SaveExamDefaultCategoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='joao', password='pass12345')

    def test_creates_default_category_when_none_selected(self):
        form = ExamForm(self.user, data={'name': 'Prova sem categoria', 'category': ''})
        self.assertTrue(form.is_valid(), form.errors)
        exam = save_exam_with_default_category_if_needed(_FakeRequest(self.user), form)
        self.assertEqual(exam.category.name, '~ sem categoria')
        self.assertEqual(exam.user, self.user)

    def test_reuses_existing_default_category(self):
        Category.objects.create(user=self.user, name='~ sem categoria')
        form = ExamForm(self.user, data={'name': 'Outra prova', 'category': ''})
        self.assertTrue(form.is_valid(), form.errors)
        save_exam_with_default_category_if_needed(_FakeRequest(self.user), form)
        self.assertEqual(Category.objects.filter(user=self.user, name='~ sem categoria').count(), 1)

    def test_keeps_explicit_category_when_provided(self):
        cat = Category.objects.create(user=self.user, name='Matemática')
        form = ExamForm(self.user, data={'name': 'Prova de mat', 'category': cat.pk})
        self.assertTrue(form.is_valid(), form.errors)
        exam = save_exam_with_default_category_if_needed(_FakeRequest(self.user), form)
        self.assertEqual(exam.category, cat)


class ValidateQuestionPayloadOrchestrationTests(TestCase):
    """Testa a parte que pertence a utils.py: campos comuns + roteamento.
    Usa 'written' apenas como tipo de exemplo para exercitar o caminho feliz
    e a delegação; regras de negócio do tipo em si já são cobertas à parte."""

    def test_raises_when_statement_or_explanation_empty(self):
        qd = make_querydict({'statement': '', 'explanation': '', 'data_answer': 'ok'})
        with self.assertRaises(ValidationError):
            validate_question_payload(Question.Types.WRITTEN, qd)

    def test_raises_when_statement_too_long(self):
        qd = make_querydict({'statement': 'a' * 1001, 'explanation': 'ok', 'data_answer': 'ok'})
        with self.assertRaises(ValidationError):
            validate_question_payload(Question.Types.WRITTEN, qd)

    def test_valid_payload_returns_cleaned_statement_and_explanation(self):
        qd = make_querydict({'statement': ' Pergunta? ', 'explanation': ' Porque sim. ', 'data_answer': 'ok'})
        stmt, expl = validate_question_payload(Question.Types.WRITTEN, qd)
        self.assertEqual(stmt, 'Pergunta?')
        self.assertEqual(expl, 'Porque sim.')

    def test_delegates_type_specific_errors_to_handler(self):
        """Confirma que erros vindos do handler (não apenas os comuns) chegam
        até quem chamou validate_question_payload."""
        qd = make_querydict({'statement': 'S', 'explanation': 'E', 'data_answer': ''})
        with self.assertRaises(ValidationError) as ctx:
            validate_question_payload(Question.Types.WRITTEN, qd)
        self.assertTrue(any('não pode ficar vazia' in m for m in ctx.exception.messages))

    def test_raises_for_unregistered_question_type(self):
        qd = make_querydict({'statement': 'S', 'explanation': 'E'})
        with self.assertRaises(ValidationError) as ctx:
            validate_question_payload('tipo_invalido', qd)
        self.assertTrue(any('inválido' in m for m in ctx.exception.messages))


class BuildQuestionEditDataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='edit', password='pass12345')
        self.category = Category.objects.create(user=self.user, name='Cat')
        self.exam = Exam.objects.create(user=self.user, category=self.category, name='Prova Edit')

    def test_delegates_to_the_correct_handler(self):
        question = TrueFalseQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', correct_answer=True
        )
        self.assertEqual(
            build_question_edit_data(question, Question.Types.TRUE_FALSE), {'correct': True}
        )


class FlattenValidationErrorsTests(TestCase):
    def test_flattens_simple_list_of_messages(self):
        exc = ValidationError(['Erro 1', 'Erro 2'])
        self.assertEqual(flatten_validation_errors(exc), ['Erro 1', 'Erro 2'])

    def test_flattens_error_dict(self):
        exc = ValidationError({'campo': ['obrigatório']})
        self.assertEqual(flatten_validation_errors(exc), ['obrigatório'])

    def test_flattens_nested_validation_errors_in_dict(self):
        exc = ValidationError({'campo': [ValidationError('erro interno')]})
        self.assertEqual(flatten_validation_errors(exc), ['erro interno'])

    def test_non_validation_error_returns_str(self):
        self.assertEqual(flatten_validation_errors(ValueError('algo deu errado')), ['algo deu errado'])

    def test_ignores_empty_messages(self):
        exc = ValidationError(['', 'Erro válido', ''])
        self.assertEqual(flatten_validation_errors(exc), ['Erro válido'])