"""
Testes unitários para exams/services.py (QuestionService)

Cobre apenas a orquestração: atribuição de order incremental, transação
atômica (rollback em erro) e delegação correta ao handler do tipo.
Regras de negócio específicas de cada tipo são testadas em
test_question_types.py — aqui usamos 'multiple_choice' apenas como
exemplo de tipo real para exercitar o fluxo ponta a ponta.
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from categories.models import Category
from exams.models import Exam, Question, MultipleChoiceQuestion
from exams.services import QuestionService
from .test_support import make_querydict


class QuestionServiceCreateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='svc', password='pass12345')
        self.category = Category.objects.create(user=self.user, name='Cat')
        self.exam = Exam.objects.create(user=self.user, category=self.category, name='Prova Svc')

    def test_create_multiple_choice_question_end_to_end(self):
        post = make_querydict({
            'statement': 'Qual a capital da França?',
            'explanation': 'Paris é a capital da França.',
            'data_options': ['Paris', 'Londres', 'Roma'],
            'data_correct': '0',
        })
        q = QuestionService.create_question(self.exam, Question.Types.MULTIPLE_CHOICE, post)

        self.assertIsInstance(q, MultipleChoiceQuestion)
        self.assertEqual(q.exam, self.exam)
        self.assertEqual(q.order, 0)
        self.assertEqual(q.options.count(), 3)

    def test_create_sets_incremental_order(self):
        post = lambda correct: make_querydict({
            'statement': 'P', 'explanation': 'E', 'data_options': ['A', 'B'], 'data_correct': correct,
        })
        q1 = QuestionService.create_question(self.exam, Question.Types.MULTIPLE_CHOICE, post('0'))
        q2 = QuestionService.create_question(self.exam, Question.Types.MULTIPLE_CHOICE, post('1'))
        self.assertEqual((q1.order, q2.order), (0, 1))

    def test_create_rolls_back_when_dependencies_invalid(self):
        post = make_querydict({
            'statement': 'Relacione os pares',
            'explanation': 'Explicação válida',
            'data_pairs_left': ['A', 'B'],
            'data_pairs_right': ['1'],
        })
        with self.assertRaises(ValidationError):
            QuestionService.create_question(self.exam, Question.Types.MATCHING, post)
        self.assertEqual(self.exam.questions.count(), 0)

    def test_create_raises_validation_error_for_unregistered_type(self):
        post = make_querydict({'statement': 'S', 'explanation': 'E'})
        with self.assertRaises(ValidationError):
            QuestionService.create_question(self.exam, 'tipo_invalido', post)

    def test_create_delegates_to_handler_returned_by_get_handler(self):
        """Isolamento puro: comprova que o serviço (e a validação que ele
        dispara) não conhece nenhuma regra de tipo — chamam só o que o
        handler mockado devolve. Como get_handler é importado tanto em
        utils.py (validate_question_payload) quanto em services.py, os
        dois pontos de importação precisam ser substituídos juntos."""
        fake_handler = MagicMock()
        fake_handler.build_instance.return_value = MultipleChoiceQuestion(statement='s', explanation='e')

        post = make_querydict({
            'statement': 'S', 'explanation': 'E', 'data_options': ['A', 'B'], 'data_correct': '0',
        })
        with patch('exams.services.get_handler', return_value=fake_handler), \
            patch('exams.utils.get_handler', return_value=fake_handler):
            question = QuestionService.create_question(self.exam, Question.Types.MULTIPLE_CHOICE, post)

        fake_handler.validate.assert_called_once()
        fake_handler.build_instance.assert_called_once()
        fake_handler.save_dependencies.assert_called_once_with(question, post)

class QuestionServiceUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='svcu', password='pass12345')
        self.category = Category.objects.create(user=self.user, name='Cat')
        self.exam = Exam.objects.create(user=self.user, category=self.category, name='Prova SvcU')
        create_post = make_querydict({
            'statement': 'Original', 'explanation': 'Original exp',
            'data_options': ['A', 'B'], 'data_correct': '0',
        })
        self.question = QuestionService.create_question(self.exam, Question.Types.MULTIPLE_CHOICE, create_post)

    def test_update_changes_statement_explanation_and_options(self):
        update_post = make_querydict({
            'statement': 'Atualizado', 'explanation': 'Explicação atualizada',
            'data_options': ['X', 'Y', 'Z'], 'data_correct': '2',
        })
        updated = QuestionService.update_question(self.question, Question.Types.MULTIPLE_CHOICE, update_post)
        updated.refresh_from_db()
        self.assertEqual(updated.statement, 'Atualizado')
        self.assertEqual(updated.options.count(), 3)

    def test_update_rolls_back_when_invalid(self):
        update_post = make_querydict({
            'statement': 'Atualizado', 'explanation': 'Explicação atualizada',
            'data_options': ['Única'], 'data_correct': '0',
        })
        with self.assertRaises(ValidationError):
            QuestionService.update_question(self.question, Question.Types.MULTIPLE_CHOICE, update_post)
        self.question.refresh_from_db()
        self.assertEqual(self.question.statement, 'Original')

    def test_update_delegates_to_handler_returned_by_get_handler(self):
        fake_handler = MagicMock()
        update_post = make_querydict({
            'statement': 'S', 'explanation': 'E', 'data_options': ['A', 'B'], 'data_correct': '0',
        })
        with patch('exams.services.get_handler', return_value=fake_handler), \
            patch('exams.utils.get_handler', return_value=fake_handler):
            QuestionService.update_question(self.question, Question.Types.MULTIPLE_CHOICE, update_post)

        fake_handler.validate.assert_called_once()
        fake_handler.update_dependencies.assert_called_once_with(self.question, update_post)