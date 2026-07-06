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
 
 
class LoginRequiredTests(ExamsViewsTestCaseBase):
    """Garante que todas as views exigem autenticação."""
 
    def setUp(self):
        super().setUp()
        self.client.logout()
 
    def test_exam_create_requires_login(self):
        resp = self.client.get(reverse('exams:create'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.url if hasattr(resp, 'url') else '')
 
    def test_exam_edit_requires_login(self):
        resp = self.client.get(reverse('exams:edit', args=[self.exam.pk]))
        self.assertEqual(resp.status_code, 302)
 
    def test_exam_detail_json_requires_login(self):
        resp = self.client.get(reverse('exams:detail_json', args=[self.exam.pk]))
        self.assertEqual(resp.status_code, 302)
 
    def test_exam_delete_requires_login(self):
        resp = self.client.delete(reverse('exams:delete', args=[self.exam.pk]))
        self.assertEqual(resp.status_code, 302)
 
    def test_question_add_requires_login(self):
        resp = self.client.get(reverse('exams:question_add', args=[self.exam.pk]))
        self.assertEqual(resp.status_code, 302)
 
 
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
        # nome vazio é inválido (obrigatório)
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
 
 
class ExamDetailJsonViewTests(ExamsViewsTestCaseBase):
    @patch('exams.views.urgency_color', return_value='green')
    @patch('exams.views.get_urgency_ratio', return_value=0.1)
    def test_json_shape_without_attempts(self, mock_ratio, mock_color):
        resp = self.client.get(reverse('exams:detail_json', args=[self.exam.pk]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
 
        self.assertEqual(data['id'], self.exam.pk)
        self.assertEqual(data['name'], self.exam.name)
        self.assertEqual(data['category'], self.category.name)
        self.assertEqual(data['question_count'], 0)
        self.assertEqual(data['attempt_count'], 0)
        self.assertIsNone(data['last_attempt_date'])
        self.assertIsNone(data['last_duration'])
        self.assertIsNone(data['avg_duration'])
        self.assertIsNone(data['score_percent'])
        self.assertEqual(data['urgency_color'], 'green')
        self.assertEqual(data['urgency_ratio'], 0.1)
 
    @patch('exams.views.urgency_color', return_value='red')
    @patch('exams.views.get_urgency_ratio', return_value=0.9)
    def test_json_shape_with_attempts(self, mock_ratio, mock_color):
        """Usa um mock leve para o Attempt para não depender de campos internos
        da app `attempts`, que não faz parte do escopo desta suíte."""
        fake_attempt = _FakeAttempt(
            score_percent_value=75.0,
            duration=timedelta(minutes=3, seconds=15),
        )
        fake_queryset = _FakeAttemptQuerySet(
            all_attempts=[fake_attempt], avg_duration=fake_attempt.duration
        )
 
        with patch('exams.views.Attempt') as MockAttempt:
            MockAttempt.objects.filter.return_value = fake_queryset
            resp = self.client.get(reverse('exams:detail_json', args=[self.exam.pk]))
 
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['attempt_count'], 1)
        self.assertEqual(data['score_percent'], 75.0)
        self.assertEqual(data['last_duration'], '3min 15s')
        self.assertEqual(data['avg_duration'], '3min 15s')
        self.assertEqual(data['urgency_color'], 'red')
 
    def test_returns_404_for_exam_of_another_user(self):
        other_exam = Exam.objects.create(user=self.other_user, name='Prova do Pedro Detail')
        resp = self.client.get(reverse('exams:detail_json', args=[other_exam.pk]))
        self.assertEqual(resp.status_code, 404)
 
 
class _FakeAttempt:
    """Stub mínimo com apenas a interface usada por exam_detail_json."""
    def __init__(self, score_percent_value, duration):
        from django.utils import timezone
        self.started_at = timezone.now()
        self.duration = duration
        self._score_percent_value = score_percent_value
 
    def score_percent(self):
        return self._score_percent_value
 
 
class _FakeAttemptQuerySet:
    """Stub mínimo simulando o encadeamento de QuerySet usado na view."""
    def __init__(self, all_attempts, avg_duration):
        self._all = all_attempts
        self._avg_duration = avg_duration
 
    def count(self):
        return len(self._all)
 
    def order_by(self, *args, **kwargs):
        return self
 
    def first(self):
        return self._all[0] if self._all else None
 
    def filter(self, *args, **kwargs):
        return self
 
    def aggregate(self, **kwargs):
        return {'avg': self._avg_duration}
 
 
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
 
    def test_get_with_valid_type_query_param_shows_full_form(self):
        url = reverse('exams:question_add', args=[self.exam.pk]) + '?question_type=true_false'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['question_type'], 'true_false')

    def test_get_renders_question_panels_without_inline_hidden_style(self):
        url = reverse('exams:question_add', args=[self.exam.pk]) + '?question_type=multiple_choice'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="panel-multiple_choice"')
        self.assertContains(resp, 'id="panel-multi_answer"')
        self.assertNotContains(resp, 'id="panel-multiple_choice" style="display: none;"')

    def test_post_valid_multiple_choice_creates_question_and_redirects(self):
        url = reverse('exams:question_add', args=[self.exam.pk]) + '?question_type=multiple_choice'
        resp = self.client.post(url, {
            'question_type': 'multiple_choice',
            'statement': 'Qual o maior planeta?',
            'explanation': 'Júpiter é o maior planeta do sistema solar.',
            'data_options': ['Júpiter', 'Marte', 'Vênus'],
            'data_correct': '0',
        })
        self.assertRedirects(resp, reverse('exams:edit', args=[self.exam.pk]))
        self.assertEqual(self.exam.questions.count(), 1)
        q = MultipleChoiceQuestion.objects.get(exam=self.exam)
        self.assertEqual(q.options.count(), 3)
 
    def test_post_invalid_shows_errors_and_does_not_create(self):
        url = reverse('exams:question_add', args=[self.exam.pk]) + '?question_type=written'
        resp = self.client.post(url, {
            'question_type': 'written',
            'statement': 'Pergunta',
            'explanation': 'Explicação',
            'data_answer': '',  # inválido: resposta vazia
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.context['errors']) > 0)
        self.assertEqual(self.exam.questions.count(), 0)
 
    def test_returns_404_for_exam_of_another_user(self):
        other_exam = Exam.objects.create(user=self.other_user, name='Prova do Pedro Add')
        resp = self.client.get(reverse('exams:question_add', args=[other_exam.pk]))
        self.assertEqual(resp.status_code, 404)
 
 
class QuestionEditViewTests(ExamsViewsTestCaseBase):
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
 
    def test_post_updates_question(self):
        resp = self.client.post(
            reverse('exams:question_edit', args=[self.exam.pk, self.question.pk]),
            {
                'statement': 'O sol é uma estrela? (atualizado)',
                'explanation': 'Sim, confirmado.',
                'data_correct': 'false',
            },
        )
        self.assertRedirects(resp, reverse('exams:edit', args=[self.exam.pk]))
        self.question.refresh_from_db()
        self.assertEqual(self.question.statement, 'O sol é uma estrela? (atualizado)')
        self.assertFalse(self.question.truefalsequestion.correct_answer)
 
    def test_post_without_data_prefixed_fields_does_not_update(self):
        """Sem nenhuma chave 'data_*' no POST, a view não tenta atualizar
        os dados dinâmicos (apenas reexibe o formulário)."""
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
 
