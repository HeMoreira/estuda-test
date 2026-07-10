"""
Testes de fluxo completo (integração) para exams/views.py
 
Cobre, via Django test Client:
- Proteção @login_required em todas as views
- exam_create: GET, POST válido (redirect + criação), POST inválido
- exam_edit: GET (contexto/questions), POST de atualização, isolamento por usuário (404)
- exam_detail_json: shape do JSON retornado (com mocks para Attempt e spaced_repetition,
  já que os detalhes internos dessas dependências não fazem parte da app `exams`)
- exam_delete: DELETE remove o registro
- question_add: fluxo de seleção de tipo (GET/POST) + criação de questão + erros de validação
- question_edit: pré-preenchimento (question_data_json) + atualização + isolamento por exam
- question_delete: remoção + reindexação da ordem das questões restantes
"""
from datetime import timedelta
from unittest.mock import patch
 
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
 
from categories.models import Category
from exams.models import (
    Exam,
    Question,
    MultipleChoiceQuestion,
    MultiAnswerQuestion,
    WrittenQuestion,
    MatchingQuestion,
    MatchingPair,
    FlashcardQuestion,
    QuestionOption,
    TrueFalseQuestion,
    OrderingQuestion,
    OrderingItem,
)

class ExamsViewsTestCaseBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='maria', password='pass12345')
        self.other_user = User.objects.create_user(username='pedro', password='pass12345')
        self.category = Category.objects.create(user=self.user, name='Geografia')
        self.exam = Exam.objects.create(user=self.user, category=self.category, name='Prova de Geo')
        self.client.login(username='maria', password='pass12345')

class ExamCreateViewTests(ExamsViewsTestCaseBase):
    def test_get_renders_empty_form(self):
        resp = self.client.get(reverse('exams:create'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'exams/exam_form.html')
        self.assertEqual(resp.context['action'], 'create')

    def test_post_valid_creates_exam_and_redirects(self):
        resp = self.client.post(reverse('exams:create'), {
            'name': 'Nova Prova de História',
            'category': '',
        })
        exam = Exam.objects.get(name='Nova Prova de História')
        self.assertEqual(exam.user, self.user)
        self.assertRedirects(resp, reverse('exams:edit', args=[exam.pk]))

    def test_post_invalid_shows_errors(self):
        resp = self.client.post(reverse('exams:create'), {'name': '', 'category': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['form'].is_valid())

    def test_post_duplicate_name_is_invalid(self):
        resp = self.client.post(reverse('exams:create'), {
            'name': self.exam.name,  # nome já usado (unique=True)
            'category': '',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['form'].is_valid())

class ExamEditViewTests(ExamsViewsTestCaseBase):
    def test_get_shows_exam_and_questions(self):
        MultipleChoiceQuestion.objects.create(
            exam=self.exam, statement='Pergunta 1', explanation='Exp 1'
        )
        resp = self.client.get(reverse('exams:edit', args=[self.exam.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['exam'], self.exam)
        self.assertEqual(len(resp.context['questions']), 1)

    def test_post_updates_exam_name(self):
        resp = self.client.post(reverse('exams:edit', args=[self.exam.pk]), {
            'name': 'Nome Atualizado',
            'category': '',
        })
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.name, 'Nome Atualizado')
        self.assertRedirects(resp, reverse('exams:edit', args=[self.exam.pk]))

    def test_returns_404_for_exam_of_another_user(self):
        other_exam = Exam.objects.create(user=self.other_user, name='Prova do Pedro')
        resp = self.client.get(reverse('exams:edit', args=[other_exam.pk]))
        self.assertEqual(resp.status_code, 404)
 
class ExamDeleteViewTests(ExamsViewsTestCaseBase):
    def test_delete_removes_exam(self):
        resp = self.client.delete(reverse('exams:delete', args=[self.exam.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'ok': True})
        self.assertFalse(Exam.objects.filter(pk=self.exam.pk).exists())
 
    def test_returns_404_for_exam_of_another_user(self):
        other_exam = Exam.objects.create(user=self.other_user, name='Prova do Pedro Delete')
        resp = self.client.delete(reverse('exams:delete', args=[other_exam.pk]))
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Exam.objects.filter(pk=other_exam.pk).exists())
 
    def test_get_method_not_allowed(self):
        resp = self.client.get(reverse('exams:delete', args=[self.exam.pk]))
        self.assertEqual(resp.status_code, 405)



class QuestionAddViewTests(ExamsViewsTestCaseBase):
    """Comportamentos transversais do fluxo de adição, independentes do
    tipo de questão. Os fluxos específicos de criação por tipo estão em
    QuestionCreateEditTestMixin (abaixo)."""

    def test_get_without_type_shows_type_selection_form(self):
        resp = self.client.get(reverse('exams:question_add', args=[self.exam.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('type_form', resp.context)
        self.assertNotIn('form', resp.context)

    def test_post_without_question_type_rerenders_type_selection(self):
        """Sem 'question_type' em POST nem GET, a view deve apenas
        re-renderizar a tela de seleção de tipo (sem criar nada)."""
        resp = self.client.post(reverse('exams:question_add', args=[self.exam.pk]), {})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('type_form', resp.context)
        self.assertNotIn('form', resp.context)
        self.assertEqual(self.exam.questions.count(), 0)

    def test_get_renders_question_panels_without_inline_hidden_style(self):
        url = reverse('exams:question_add', args=[self.exam.pk]) + '?question_type=multiple_choice'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="panel-multiple_choice"')
        self.assertContains(resp, 'id="panel-multi_answer"')
        self.assertNotContains(resp, 'id="panel-multiple_choice" style="display: none;"')

    def test_returns_404_for_exam_of_another_user(self):
        other_exam = Exam.objects.create(user=self.other_user, name='Prova do Pedro Add')
        resp = self.client.get(reverse('exams:question_add', args=[other_exam.pk]))
        self.assertEqual(resp.status_code, 404)

class QuestionEditViewTests(ExamsViewsTestCaseBase):
    """Comportamentos transversais do fluxo de edição, independentes do
    tipo de questão. Os fluxos específicos de atualização por tipo estão em
    QuestionCreateEditTestMixin (abaixo)."""

    def setUp(self):
        super().setUp()
        self.question = TrueFalseQuestion.objects.create(
            exam=self.exam,
            statement='O sol é uma estrela?',
            explanation='Sim, o sol é uma estrela.',
            correct_answer=True,
        )

    def test_get_prefills_question_data(self):
        resp = self.client.get(
            reverse('exams:question_edit', args=[self.exam.pk, self.question.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('"correct": true', resp.context['question_data_json'])

    def test_post_without_data_prefixed_fields_does_not_update(self):
        """Sem nenhuma chave 'data_*' no POST, a view não deve conseguir
        atualizar os dados dinâmicos (a validação do tipo deve barrar)."""
        resp = self.client.post(
            reverse('exams:question_edit', args=[self.exam.pk, self.question.pk]),
            {'statement': 'Não deveria salvar', 'explanation': 'Não deveria salvar'},
        )
        self.assertEqual(resp.status_code, 200)
        self.question.refresh_from_db()
        self.assertEqual(self.question.statement, 'O sol é uma estrela?')

    def test_returns_404_when_question_belongs_to_other_exam(self):
        other_exam = Exam.objects.create(user=self.user, name='Outra prova qualquer')
        resp = self.client.get(
            reverse('exams:question_edit', args=[other_exam.pk, self.question.pk])
        )
        self.assertEqual(resp.status_code, 404)

    def test_returns_404_for_exam_of_another_user(self):
        other_exam = Exam.objects.create(user=self.other_user, name='Prova do Pedro Edit')
        other_question = TrueFalseQuestion.objects.create(
            exam=other_exam, statement='s', explanation='e', correct_answer=True
        )
        resp = self.client.get(
            reverse('exams:question_edit', args=[other_exam.pk, other_question.pk])
        )
        self.assertEqual(resp.status_code, 404)

class QuestionCreateEditTestMixin:
    """Mixin parametrizado por tipo de questão. Reaproveita a mesma bateria
    de testes (criação válida/inválida, exibição do painel correto, edição
    válida, pré-preenchimento) para os 7 tipos suportados — a única coisa
    que muda entre eles são os payloads e as asserções de conteúdo,
    definidos em cada subclasse concreta abaixo."""

    type_value = None
    model_class = None

    # ── Pontos de extensão (implementados por subclasse) ──
    def valid_payload(self):
        raise NotImplementedError

    def invalid_payload(self):
        raise NotImplementedError

    def assert_created_correctly(self, question):
        raise NotImplementedError

    def create_instance_for_edit(self):
        raise NotImplementedError

    def edit_payload(self):
        raise NotImplementedError

    def assert_updated_correctly(self, question):
        raise NotImplementedError

    # ── Helpers ──
    def add_url(self):
        return reverse('exams:question_add', args=[self.exam.pk]) + f'?question_type={self.type_value}'

    def edit_url(self, question):
        return reverse('exams:question_edit', args=[self.exam.pk, question.pk])

    # ── Criação ──
    def test_add_get_shows_type_and_correct_panel(self):
        resp = self.client.get(self.add_url())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['question_type'], self.type_value)
        self.assertContains(resp, f'id="panel-{self.type_value}"')

    def test_add_valid_payload_creates_question_and_redirects(self):
        resp = self.client.post(self.add_url(), self.valid_payload())
        self.assertRedirects(resp, reverse('exams:edit', args=[self.exam.pk]))
        self.assertEqual(self.exam.questions.count(), 1)
        question = self.model_class.objects.get(exam=self.exam)
        self.assert_created_correctly(question)

    def test_add_invalid_payload_shows_errors_and_does_not_create(self):
        resp = self.client.post(self.add_url(), self.invalid_payload())
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.context['errors']) > 0)
        self.assertEqual(self.exam.questions.count(), 0)

    # ── Edição ──
    def test_edit_get_prefills_type_and_data(self):
        question = self.create_instance_for_edit()
        resp = self.client.get(self.edit_url(question))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['question_type'], self.type_value)
        self.assertIn('question_data_json', resp.context)

    def test_edit_valid_payload_updates_question_and_redirects(self):
        question = self.create_instance_for_edit()
        resp = self.client.post(self.edit_url(question), self.edit_payload())
        self.assertRedirects(resp, reverse('exams:edit', args=[self.exam.pk]))
        question.refresh_from_db()
        self.assert_updated_correctly(question)

    def test_edit_invalid_payload_shows_errors_and_does_not_update(self):
        question = self.create_instance_for_edit()
        original_statement = question.statement
        resp = self.client.post(self.edit_url(question), self.invalid_payload())
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.context['errors']) > 0)
        question.refresh_from_db()
        self.assertEqual(question.statement, original_statement)

# ── Múltipla escolha ──
class MultipleChoiceViewFlowTests(QuestionCreateEditTestMixin, ExamsViewsTestCaseBase):
    type_value = Question.Types.MULTIPLE_CHOICE
    model_class = MultipleChoiceQuestion

    def valid_payload(self):
        return {
            'question_type': self.type_value,
            'statement': 'Qual o maior planeta?',
            'explanation': 'Júpiter é o maior planeta do sistema solar.',
            'data_options': ['Júpiter', 'Marte', 'Vênus'],
            'data_correct': '0',
        }

    def invalid_payload(self):
        return {
            'question_type': self.type_value,
            'statement': 'Pergunta',
            'explanation': 'Explicação',
            'data_options': ['Única'],
            'data_correct': '0',
        }

    def assert_created_correctly(self, question):
        options = list(question.options.order_by('order'))
        self.assertEqual(len(options), 3)
        self.assertTrue(options[0].is_correct)

    def create_instance_for_edit(self):
        question = MultipleChoiceQuestion.objects.create(
            exam=self.exam, statement='Original', explanation='Exp original'
        )
        QuestionOption.objects.create(question=question, text='A', is_correct=True, order=0)
        QuestionOption.objects.create(question=question, text='B', is_correct=False, order=1)
        return question

    def edit_payload(self):
        return {
            'statement': 'Atualizada',
            'explanation': 'Exp atualizada',
            'data_options': ['X', 'Y', 'Z'],
            'data_correct': '2',
        }

    def assert_updated_correctly(self, question):
        self.assertEqual(question.statement, 'Atualizada')
        options = list(question.options.order_by('order'))
        self.assertEqual([o.text for o in options], ['X', 'Y', 'Z'])
        self.assertTrue(options[2].is_correct)

# ── Resposta múltipla ──
class MultiAnswerViewFlowTests(QuestionCreateEditTestMixin, ExamsViewsTestCaseBase):
    type_value = Question.Types.MULTI_ANSWER
    model_class = MultiAnswerQuestion

    def valid_payload(self):
        return {
            'question_type': self.type_value,
            'statement': 'Quais são primos?',
            'explanation': '2 e 3 são primos.',
            'data_options': ['2', '3', '4'],
            'data_correct': ['0', '1'],
        }

    def invalid_payload(self):
        return {
            'question_type': self.type_value,
            'statement': 'Pergunta',
            'explanation': 'Explicação',
            'data_options': ['A', 'B'],
            # sem data_correct: nenhuma marcada como correta
        }

    def assert_created_correctly(self, question):
        options = list(question.options.order_by('order'))
        self.assertEqual([o.is_correct for o in options], [True, True, False])

    def create_instance_for_edit(self):
        question = MultiAnswerQuestion.objects.create(
            exam=self.exam, statement='Original', explanation='Exp original'
        )
        QuestionOption.objects.create(question=question, text='A', is_correct=True, order=0)
        QuestionOption.objects.create(question=question, text='B', is_correct=False, order=1)
        return question

    def edit_payload(self):
        return {
            'statement': 'Atualizada',
            'explanation': 'Exp atualizada',
            'data_options': ['X', 'Y', 'Z'],
            'data_correct': ['1', '2'],
        }

    def assert_updated_correctly(self, question):
        self.assertEqual(question.statement, 'Atualizada')
        options = list(question.options.order_by('order'))
        self.assertEqual([o.is_correct for o in options], [False, True, True])

# ── Verdadeiro ou falso ──
class TrueFalseViewFlowTests(QuestionCreateEditTestMixin, ExamsViewsTestCaseBase):
    type_value = Question.Types.TRUE_FALSE
    model_class = TrueFalseQuestion

    def valid_payload(self):
        return {
            'question_type': self.type_value,
            'statement': 'A Terra é redonda?',
            'explanation': 'Sim, aproximadamente esférica.',
            'data_correct': 'true',
        }

    def invalid_payload(self):
        return {
            'question_type': self.type_value,
            'statement': 'Pergunta',
            'explanation': 'Explicação',
            'data_correct': 'talvez',
        }

    def assert_created_correctly(self, question):
        self.assertTrue(question.truefalsequestion.correct_answer)

    def create_instance_for_edit(self):
        return TrueFalseQuestion.objects.create(
            exam=self.exam, statement='Original', explanation='Exp original', correct_answer=True
        )

    def edit_payload(self):
        return {'statement': 'Atualizada', 'explanation': 'Exp atualizada', 'data_correct': 'false'}

    def assert_updated_correctly(self, question):
        self.assertEqual(question.statement, 'Atualizada')
        self.assertFalse(question.truefalsequestion.correct_answer)

# ── Resposta escrita ──
class WrittenViewFlowTests(QuestionCreateEditTestMixin, ExamsViewsTestCaseBase):
    type_value = Question.Types.WRITTEN
    model_class = WrittenQuestion

    def valid_payload(self):
        return {
            'question_type': self.type_value,
            'statement': 'Capital da França?',
            'explanation': 'É Paris.',
            'data_answer': 'Paris',
        }

    def invalid_payload(self):
        return {
            'question_type': self.type_value,
            'statement': 'Pergunta',
            'explanation': 'Explicação',
            'data_answer': '',
        }

    def assert_created_correctly(self, question):
        self.assertEqual(question.writtenquestion.expected_answer, 'Paris')

    def create_instance_for_edit(self):
        return WrittenQuestion.objects.create(
            exam=self.exam, statement='Original', explanation='Exp original', expected_answer='Antigo'
        )

    def edit_payload(self):
        return {'statement': 'Atualizada', 'explanation': 'Exp atualizada', 'data_answer': 'Novo'}

    def assert_updated_correctly(self, question):
        self.assertEqual(question.statement, 'Atualizada')
        self.assertEqual(question.writtenquestion.expected_answer, 'Novo')

# ── Ordenar elementos ──
class OrderingViewFlowTests(QuestionCreateEditTestMixin, ExamsViewsTestCaseBase):
    type_value = Question.Types.ORDERING
    model_class = OrderingQuestion

    def valid_payload(self):
        return {
            'question_type': self.type_value,
            'statement': 'Ordene os planetas mais próximos do Sol',
            'explanation': 'Mercúrio, Vênus, Terra.',
            'data_items': ['Mercúrio', 'Vênus', 'Terra'],
        }

    def invalid_payload(self):
        return {
            'question_type': self.type_value,
            'statement': 'Ordene',
            'explanation': 'Exp',
            'data_items': ['Único'],
        }

    def assert_created_correctly(self, question):
        items = list(question.items.order_by('position'))
        self.assertEqual([i.text for i in items], ['Mercúrio', 'Vênus', 'Terra'])

    def create_instance_for_edit(self):
        question = OrderingQuestion.objects.create(
            exam=self.exam, statement='Original', explanation='Exp original'
        )
        OrderingItem.objects.create(question=question, text='Velho1', position=1)
        OrderingItem.objects.create(question=question, text='Velho2', position=2)
        return question

    def edit_payload(self):
        return {
            'statement': 'Atualizada',
            'explanation': 'Exp atualizada',
            'data_items': ['Novo1', 'Novo2', 'Novo3'],
        }

    def assert_updated_correctly(self, question):
        self.assertEqual(question.statement, 'Atualizada')
        items = list(question.items.order_by('position'))
        self.assertEqual([i.text for i in items], ['Novo1', 'Novo2', 'Novo3'])

# ── Relacionar colunas ──
class MatchingViewFlowTests(QuestionCreateEditTestMixin, ExamsViewsTestCaseBase):
    type_value = Question.Types.MATCHING
    model_class = MatchingQuestion

    def valid_payload(self):
        return {
            'question_type': self.type_value,
            'statement': 'Relacione países e capitais',
            'explanation': 'Associações corretas.',
            'data_pairs_left': ['Brasil', 'França'],
            'data_pairs_right': ['Brasília', 'Paris'],
        }

    def invalid_payload(self):
        return {
            'question_type': self.type_value,
            'statement': 'Relacione',
            'explanation': 'Exp',
            'data_pairs_left': ['A', 'B'],
            'data_pairs_right': ['1'],
        }

    def assert_created_correctly(self, question):
        pairs = list(question.pairs.order_by('order'))
        self.assertEqual([(p.left, p.right) for p in pairs], [('Brasil', 'Brasília'), ('França', 'Paris')])

    def create_instance_for_edit(self):
        question = MatchingQuestion.objects.create(
            exam=self.exam, statement='Original', explanation='Exp original'
        )
        MatchingPair.objects.create(question=question, left='A', right='1', order=0)
        return question

    def edit_payload(self):
        return {
            'statement': 'Atualizada',
            'explanation': 'Exp atualizada',
            'data_pairs_left': ['X', 'Y'],
            'data_pairs_right': ['1', '2'],
        }

    def assert_updated_correctly(self, question):
        self.assertEqual(question.statement, 'Atualizada')
        pairs = list(question.pairs.order_by('order'))
        self.assertEqual([p.left for p in pairs], ['X', 'Y'])

# ── Flashcard ──
class FlashcardViewFlowTests(QuestionCreateEditTestMixin, ExamsViewsTestCaseBase):
    type_value = Question.Types.FLASHCARD
    model_class = FlashcardQuestion

    def valid_payload(self):
        return {
            'question_type': self.type_value,
            'statement': 'Card de fotossíntese',
            'explanation': 'Conceito básico de biologia.',
            'data_front': 'O que é fotossíntese?',
            'data_back': 'Processo de conversão de luz em energia química.',
        }

    def invalid_payload(self):
        return {
            'question_type': self.type_value,
            'statement': 'Card',
            'explanation': 'Exp',
            'data_front': 'Frente',
            'data_back': '',
        }

    def assert_created_correctly(self, question):
        self.assertEqual(question.flashcardquestion.front, 'O que é fotossíntese?')
        self.assertTrue(question.flashcardquestion.back.startswith('Processo'))

    def create_instance_for_edit(self):
        return FlashcardQuestion.objects.create(
            exam=self.exam, statement='Original', explanation='Exp original', front='F', back='B'
        )

    def edit_payload(self):
        return {
            'statement': 'Atualizada',
            'explanation': 'Exp atualizada',
            'data_front': 'Novo front',
            'data_back': 'Novo back',
        }

    def assert_updated_correctly(self, question):
        self.assertEqual(question.statement, 'Atualizada')
        self.assertEqual(question.flashcardquestion.front, 'Novo front')
        self.assertEqual(question.flashcardquestion.back, 'Novo back')

class QuestionDeleteViewTests(ExamsViewsTestCaseBase):
    def setUp(self):
        super().setUp()
        self.q1 = TrueFalseQuestion.objects.create(
            exam=self.exam, statement='Q1', explanation='E1', correct_answer=True, order=0
        )
        self.q2 = TrueFalseQuestion.objects.create(
            exam=self.exam, statement='Q2', explanation='E2', correct_answer=True, order=1
        )
        self.q3 = TrueFalseQuestion.objects.create(
            exam=self.exam, statement='Q3', explanation='E3', correct_answer=True, order=2
        )
 
    def test_delete_removes_question(self):
        resp = self.client.delete(
            reverse('exams:question_delete', args=[self.exam.pk, self.q2.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Question.objects.filter(pk=self.q2.pk).exists())
 
    def test_delete_reindexes_remaining_question_order(self):
        self.client.delete(reverse('exams:question_delete', args=[self.exam.pk, self.q1.pk]))
        remaining = list(self.exam.questions.order_by('order'))
        self.assertEqual([q.pk for q in remaining], [self.q2.pk, self.q3.pk])
        self.assertEqual([q.order for q in remaining], [0, 1])
 
    def test_returns_404_when_question_belongs_to_other_exam(self):
        other_exam = Exam.objects.create(user=self.user, name='Outra prova delete')
        resp = self.client.delete(
            reverse('exams:question_delete', args=[other_exam.pk, self.q1.pk])
        )
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Question.objects.filter(pk=self.q1.pk).exists())



class FullExamCreationFlowIntegrationTest(ExamsViewsTestCaseBase):
    """Teste de fluxo ponta a ponta: criar prova -> adicionar múltiplas
    questões de tipos diferentes -> editar uma -> remover outra -> conferir estado final."""
 
    def test_full_flow(self):
        # 1. Cria a prova
        resp = self.client.post(reverse('exams:create'), {
            'name': 'Prova Integrada', 'category': '',
        })
        exam = Exam.objects.get(name='Prova Integrada')
        self.assertRedirects(resp, reverse('exams:edit', args=[exam.pk]))
 
        # 2. Adiciona uma questão de múltipla escolha
        url_mc = reverse('exams:question_add', args=[exam.pk]) + '?question_type=multiple_choice'
        self.client.post(url_mc, {
            'question_type': 'multiple_choice',
            'statement': 'Q Multipla',
            'explanation': 'Exp',
            'data_options': ['A', 'B'],
            'data_correct': '0',
        })
 
        # 3. Adiciona uma questão de ordenação
        url_ord = reverse('exams:question_add', args=[exam.pk]) + '?question_type=ordering'
        self.client.post(url_ord, {
            'question_type': 'ordering',
            'statement': 'Ordene os itens',
            'explanation': 'Exp ord',
            'data_items': ['Primeiro', 'Segundo'],
        })
 
        exam.refresh_from_db()
        self.assertEqual(exam.question_count(), 2)
 
        ordering_question = OrderingQuestion.objects.get(exam=exam)
        self.assertEqual(ordering_question.items.count(), 2)
 
        # 4. Edita a questão de múltipla escolha
        mc_question = MultipleChoiceQuestion.objects.get(exam=exam)
        edit_url = reverse('exams:question_edit', args=[exam.pk, mc_question.pk])
        self.client.post(edit_url, {
            'statement': 'Q Multipla Editada',
            'explanation': 'Exp editada',
            'data_options': ['A', 'B', 'C'],
            'data_correct': '2',
        })
        mc_question.refresh_from_db()
        self.assertEqual(mc_question.statement, 'Q Multipla Editada')
        self.assertEqual(mc_question.options.count(), 3)
 
        # 5. Remove a questão de ordenação
        delete_url = reverse('exams:question_delete', args=[exam.pk, ordering_question.pk])
        self.client.delete(delete_url)
 
        exam.refresh_from_db()
        self.assertEqual(exam.question_count(), 1)
        self.assertFalse(OrderingQuestion.objects.filter(pk=ordering_question.pk).exists())
 
        # 6. Verifica JSON de detalhes (sem tentativas registradas)
        with patch('exams.views.get_urgency_ratio', return_value=0.0), \
             patch('exams.views.urgency_color', return_value='gray'):
            detail_resp = self.client.get(reverse('exams:detail_json', args=[exam.pk]))
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()['question_count'], 1)
 
        # 7. Por fim, exclui a prova inteira
        delete_exam_resp = self.client.delete(reverse('exams:delete', args=[exam.pk]))
        self.assertEqual(delete_exam_resp.status_code, 200)
        self.assertFalse(Exam.objects.filter(pk=exam.pk).exists())
