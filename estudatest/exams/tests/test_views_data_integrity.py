"""
Testes de integridade dos dados enviados pelas views para os templates.
 
Diferente de test_question_types.py (que testa cada handler isoladamente,
com instâncias já criadas em memória) e de test_views.py (que testa fluxo
de request/response, mas sem validar o CONTEÚDO de question_data_json),
este arquivo garante que o payload que efetivamente chega no template/JS
do editor — passando pela view real, pelo get_object_or_404 polimórfico e
pela serialização json.dumps — bate exatamente com o que está persistido
no banco, para os 7 tipos de questão suportados.
 
Isso existe especificamente para pegar bugs do tipo "o handler funciona
isolado, mas o dado que chega na tela está errado/vazio/desalinhado" —
categoria de erro que passou despercebida no fluxo de edição de matching.
"""
import json
 
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
 
from categories.models import Category
from exams.models import (
    Exam,
    MultipleChoiceQuestion,
    MultiAnswerQuestion,
    TrueFalseQuestion,
    WrittenQuestion,
    OrderingQuestion,
    OrderingItem,
    MatchingQuestion,
    MatchingPair,
    FlashcardQuestion,
    QuestionOption,
)
 
 
class QuestionEditDataIntegrityTests(TestCase):
    """Para cada tipo: cria a questão + dependências diretamente via ORM,
    abre a tela de edição pela view real e confere que question_data_json
    (tanto no contexto quanto no HTML efetivamente renderizado) reflete
    fielmente o que está no banco."""
 
    def setUp(self):
        self.user = User.objects.create_user(username='integridade', password='pass12345')
        self.category = Category.objects.create(user=self.user, name='Cat')
        self.exam = Exam.objects.create(user=self.user, category=self.category, name='Prova Integridade')
        self.client.login(username='integridade', password='pass12345')
 
    def _get_edit_data(self, question):
        """Faz o GET real na view de edição e devolve (response, dict já
        parseado de question_data_json). Confere também que o JSON aparece
        de fato no HTML renderizado, não só no contexto do template."""
        resp = self.client.get(reverse('exams:question_edit', args=[self.exam.pk, question.pk]))
        self.assertEqual(resp.status_code, 200)
        raw = resp.context['question_data_json']
        self.assertIsNotNone(raw)
        # Garante que o <script id="editData"> realmente contém o JSON no
        # corpo da resposta HTML (não só no contexto do template).
        self.assertContains(resp, '<script id="editData"')
        self.assertContains(resp, raw)
        return resp, json.loads(raw)
 
    # ── Múltipla escolha ──
    def test_multiple_choice_edit_data_matches_database(self):
        q = MultipleChoiceQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        QuestionOption.objects.create(question=q, text='Alfa', is_correct=False, order=0)
        QuestionOption.objects.create(question=q, text='Beta', is_correct=True, order=1)
        QuestionOption.objects.create(question=q, text='Gama', is_correct=False, order=2)
 
        _, data = self._get_edit_data(q)
        self.assertEqual(data, {'options': ['Alfa', 'Beta', 'Gama'], 'correct': 1})
 
    # ── Resposta múltipla ──
    def test_multi_answer_edit_data_matches_database(self):
        q = MultiAnswerQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        QuestionOption.objects.create(question=q, text='Alfa', is_correct=True, order=0)
        QuestionOption.objects.create(question=q, text='Beta', is_correct=False, order=1)
        QuestionOption.objects.create(question=q, text='Gama', is_correct=True, order=2)
 
        _, data = self._get_edit_data(q)
        self.assertEqual(data['options'], ['Alfa', 'Beta', 'Gama'])
        self.assertEqual(sorted(data['correct']), [0, 2])
 
    # ── Verdadeiro ou falso ──
    def test_true_false_edit_data_matches_database(self):
        q = TrueFalseQuestion.objects.create(exam=self.exam, statement='s', explanation='e', correct_answer=False)
        _, data = self._get_edit_data(q)
        self.assertEqual(data, {'correct': False})
 
    # ── Resposta escrita ──
    def test_written_edit_data_matches_database(self):
        q = WrittenQuestion.objects.create(exam=self.exam, statement='s', explanation='e', expected_answer='Paris')
        _, data = self._get_edit_data(q)
        self.assertEqual(data, {'answer': 'Paris'})
 
    # ── Ordenar elementos ──
    def test_ordering_edit_data_matches_database_in_position_order(self):
        q = OrderingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        # Cria fora de ordem de inserção para garantir que a view respeita 'position', não o pk.
        OrderingItem.objects.create(question=q, text='Terceiro', position=3)
        OrderingItem.objects.create(question=q, text='Primeiro', position=1)
        OrderingItem.objects.create(question=q, text='Segundo', position=2)
 
        _, data = self._get_edit_data(q)
        self.assertEqual(data, {'items': ['Primeiro', 'Segundo', 'Terceiro']})
 
    # ── Relacionar colunas (o caso que motivou este arquivo) ──
    def test_matching_edit_data_matches_database_in_order(self):
        q = MatchingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        # Cria fora de ordem de inserção para garantir que a view respeita 'order', não o pk.
        MatchingPair.objects.create(question=q, left='França', right='Paris', order=1)
        MatchingPair.objects.create(question=q, left='Brasil', right='Brasília', order=0)
 
        _, data = self._get_edit_data(q)
        self.assertEqual(data, {
            'pairs': [
                {'left': 'Brasil', 'right': 'Brasília'},
                {'left': 'França', 'right': 'Paris'},
            ]
        })
 
    def test_matching_edit_data_with_three_pairs_stays_aligned(self):
        """Regressão direta para o bug de desalinhamento: garante que, com
        múltiplos pares, cada 'left' aparece emparelhado com o 'right'
        correto — não com o de outra linha."""
        q = MatchingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        MatchingPair.objects.create(question=q, left='Cão', right='Late', order=0)
        MatchingPair.objects.create(question=q, left='Gato', right='Mia', order=1)
        MatchingPair.objects.create(question=q, left='Vaca', right='Muge', order=2)
 
        _, data = self._get_edit_data(q)
        pairs = {p['left']: p['right'] for p in data['pairs']}
        self.assertEqual(pairs, {'Cão': 'Late', 'Gato': 'Mia', 'Vaca': 'Muge'})
 
    # ── Flashcard ──
    def test_flashcard_edit_data_matches_database(self):
        q = FlashcardQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', front='Frente', back='Verso'
        )
        _, data = self._get_edit_data(q)
        self.assertEqual(data, {'front': 'Frente', 'back': 'Verso'})
 
    # ── Estatísticas / campos comuns que também vão para o template ──
    def test_edit_view_context_carries_correct_statement_and_explanation(self):
        q = WrittenQuestion.objects.create(
            exam=self.exam, statement='Enunciado real', explanation='Explicação real', expected_answer='ok'
        )
        resp, _ = self._get_edit_data(q)
        self.assertEqual(resp.context['statement'], 'Enunciado real')
        self.assertEqual(resp.context['explanation'], 'Explicação real')
        self.assertContains(resp, 'Enunciado real')
        self.assertContains(resp, 'Explicação real')
 
 
class QuestionPreviewDataIntegrityTests(TestCase):
    """Confere o outro lado do mesmo contrato: quando a validação falha em
    um POST de edição, o que é reexibido para o usuário (question_data_json
    vindo de build_preview_json) precisa refletir exatamente o que ele
    tinha digitado — inclusive para matching, onde o preview usa zip() cru
    (sem filtrar linhas em branco), diferente do build_edit_json."""
 
    def setUp(self):
        self.user = User.objects.create_user(username='preview', password='pass12345')
        self.category = Category.objects.create(user=self.user, name='Cat')
        self.exam = Exam.objects.create(user=self.user, category=self.category, name='Prova Preview')
        self.client.login(username='preview', password='pass12345')
 
    def test_matching_preview_after_invalid_submit_reflects_typed_values(self):
        question = MatchingQuestion.objects.create(exam=self.exam, statement='Original', explanation='Exp')
        MatchingPair.objects.create(question=question, left='A', right='1', order=0)
 
        # Submissão inválida: linha 2 só com o lado esquerdo preenchido.
        resp = self.client.post(
            reverse('exams:question_edit', args=[self.exam.pk, question.pk]),
            {
                'statement': 'Editado',
                'explanation': 'Editado exp',
                'data_pairs_left': ['Novo A', 'Novo B'],
                'data_pairs_right': ['Novo 1', ''],
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.context['errors']) > 0)
        self.assertTrue(any('linha' in e.lower() for e in resp.context['errors']))
 
        data = json.loads(resp.context['question_data_json'])
        self.assertEqual(data['pairs'][0], {'left': 'Novo A', 'right': 'Novo 1'})
 
        # Nada deve ter sido persistido.
        question.refresh_from_db()
        self.assertEqual(question.statement, 'Original')
        self.assertEqual(list(question.pairs.values_list('left', 'right')), [('A', '1')])
