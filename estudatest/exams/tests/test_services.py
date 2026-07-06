"""
Testes unitários para exams/services.py (QuestionService)
 
Cobre criação e atualização atômica de questões de cada tipo,
incluindo o rollback em caso de erro (transaction.atomic).
"""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.test import TestCase
 
from categories.models import Category
from exams.models import Exam, Question, MultipleChoiceQuestion, MatchingQuestion
from exams.services import QuestionService
 
 
def make_querydict(data):
    qd = QueryDict(mutable=True)
    for key, value in data.items():
        if isinstance(value, (list, tuple)):
            qd.setlist(key, list(value))
        else:
            qd[key] = value
    return qd
 
 
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
        self.assertTrue(q.options.get(order=0).is_correct)
 
    def test_create_sets_incremental_order(self):
        post1 = make_querydict({
            'statement': 'Pergunta 1', 'explanation': 'Exp 1',
            'data_options': ['A', 'B'], 'data_correct': '0',
        })
        post2 = make_querydict({
            'statement': 'Pergunta 2', 'explanation': 'Exp 2',
            'data_options': ['A', 'B'], 'data_correct': '1',
        })
        q1 = QuestionService.create_question(self.exam, Question.Types.MULTIPLE_CHOICE, post1)
        q2 = QuestionService.create_question(self.exam, Question.Types.MULTIPLE_CHOICE, post2)
 
        self.assertEqual(q1.order, 0)
        self.assertEqual(q2.order, 1)
 
    def test_create_rolls_back_when_dependencies_invalid(self):
        """Estatuto e explicação válidos, mas colunas de matching desbalanceadas.
        A ValidationError é levantada (seja na validação inicial, seja durante o
        processamento de dependências) e nenhuma questão deve ficar persistida,
        confirmando o comportamento atômico de create_question."""
        post = make_querydict({
            'statement': 'Relacione os pares',
            'explanation': 'Explicação válida',
            'data_pairs_left': ['A', 'B'],
            'data_pairs_right': ['1'],
        })
        with self.assertRaises(ValidationError):
            QuestionService.create_question(self.exam, Question.Types.MATCHING, post)
 
        # Nenhuma questão deve ter sido persistida devido ao rollback atômico
        self.assertEqual(self.exam.questions.count(), 0)
 
    def test_create_raises_for_invalid_question_type(self):
        post = make_querydict({'statement': 'S', 'explanation': 'E'})
        with self.assertRaises(ValidationError):
            QuestionService.create_question(self.exam, 'tipo_invalido', post)
 
 
class QuestionServiceUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='svcu', password='pass12345')
        self.category = Category.objects.create(user=self.user, name='Cat')
        self.exam = Exam.objects.create(user=self.user, category=self.category, name='Prova SvcU')
        create_post = make_querydict({
            'statement': 'Original', 'explanation': 'Original exp',
            'data_options': ['A', 'B'], 'data_correct': '0',
        })
        self.question = QuestionService.create_question(
            self.exam, Question.Types.MULTIPLE_CHOICE, create_post
        )
 
    def test_update_changes_statement_explanation_and_options(self):
        update_post = make_querydict({
            'statement': 'Atualizado',
            'explanation': 'Explicação atualizada',
            'data_options': ['X', 'Y', 'Z'],
            'data_correct': '2',
        })
        updated = QuestionService.update_question(
            self.question, Question.Types.MULTIPLE_CHOICE, update_post
        )
        updated.refresh_from_db()
        self.assertEqual(updated.statement, 'Atualizado')
        self.assertEqual(updated.explanation, 'Explicação atualizada')
        self.assertEqual(updated.options.count(), 3)
        self.assertTrue(updated.options.get(order=2).is_correct)
 
    def test_update_rolls_back_when_invalid(self):
        update_post = make_querydict({
            'statement': 'Atualizado',
            'explanation': 'Explicação atualizada',
            'data_options': ['Única'],
            'data_correct': '0',
        })
        with self.assertRaises(ValidationError):
            QuestionService.update_question(
                self.question, Question.Types.MULTIPLE_CHOICE, update_post
            )
        self.question.refresh_from_db()
        # Estatuto original deve permanecer intacto após rollback
        self.assertEqual(self.question.statement, 'Original')
