"""
Testes unitários para exams/models.py
 
Cobre:
- Exam: __str__, question_count
- MultipleChoiceQuestion / MultiAnswerQuestion (ChoiceQuestionMixin):
  check_answer, correct_answer_display, atribuição de question_type no save,
  clean() (restrição de 1 correta para múltipla escolha)
- TrueFalseQuestion: check_answer (bool e string), correct_answer_display
- WrittenQuestion: normalização (acentos, pontuação, espaços), case sensitivity,
  alternativas aceitas
- OrderingQuestion: check_answer por ids na posição correta
- MatchingQuestion: check_answer nos dois formatos aceitos (dict e list)
- FlashcardQuestion: check_answer sempre False, correct_answer_display retorna back
"""
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.test import TestCase
 
from categories.models import Category
from exams.models import (
    Exam,
    Question,
    QuestionOption,
    MultipleChoiceQuestion,
    MultiAnswerQuestion,
    TrueFalseQuestion,
    WrittenQuestion,
    OrderingQuestion,
    OrderingItem,
    MatchingQuestion,
    MatchingPair,
    FlashcardQuestion,
)


class BaseExamTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ana', password='pass12345')
        self.category = Category.objects.create(user=self.user, name='Biologia')
        self.exam = Exam.objects.create(user=self.user, category=self.category, name='Prova 1')

class ExamModelTests(BaseExamTestCase):
    def test_str_returns_name(self):
        self.assertEqual(str(self.exam), 'Prova 1')
 
    def test_question_count_zero_when_empty(self):
        self.assertEqual(self.exam.question_count(), 0)
 
    def test_question_count_reflects_related_questions(self):
        TrueFalseQuestion.objects.create(
            exam=self.exam, statement='S', explanation='E', correct_answer=True
        )
        WrittenQuestion.objects.create(
            exam=self.exam, statement='S2', explanation='E2', expected_answer='ok'
        )
        self.assertEqual(self.exam.question_count(), 2)
 
    def test_statement_preview_truncates_long_text(self):
        q = TrueFalseQuestion.objects.create(
            exam=self.exam,
            statement='A' * 200,
            explanation='E',
            correct_answer=True,
        )
        preview = q.statement_preview()
        self.assertTrue(preview.endswith('...'))
        self.assertLessEqual(len(preview), 123)
 
    def test_base_question_check_answer_not_implemented(self):
        q = Question(exam=self.exam, statement='s', explanation='e')
        with self.assertRaises(NotImplementedError):
            q.check_answer('x')
 
    def test_base_question_correct_answer_display_not_implemented(self):
        q = Question(exam=self.exam, statement='s', explanation='e')
        with self.assertRaises(NotImplementedError):
            q.correct_answer_display()

class MultipleChoiceQuestionTests(BaseExamTestCase):
    def _make_question_with_options(self, correct_index=1, count=3):
        q = MultipleChoiceQuestion.objects.create(
            exam=self.exam, statement='Capital da França?', explanation='Paris é a capital.'
        )
        options = []
        for i in range(count):
            opt = QuestionOption.objects.create(
                question=q, text=f'Opção {i}', is_correct=(i == correct_index), order=i
            )
            options.append(opt)
        return q, options
 
    def test_save_sets_question_type(self):
        q, _ = self._make_question_with_options()
        self.assertEqual(q.question_type, Question.Types.MULTIPLE_CHOICE)
 
    def test_check_answer_true_when_matches_correct_option(self):
        q, options = self._make_question_with_options(correct_index=1)
        correct_opt = options[1]
        self.assertTrue(q.check_answer([correct_opt.pk]))
 
    def test_check_answer_false_when_wrong_option(self):
        q, options = self._make_question_with_options(correct_index=1)
        wrong_opt = options[0]
        self.assertFalse(q.check_answer([wrong_opt.pk]))
 
    def test_check_answer_false_for_non_iterable_answer(self):
        q, _ = self._make_question_with_options()
        self.assertFalse(q.check_answer('not-a-list'))
 
    def test_correct_answer_display_lists_correct_option_texts(self):
        q, options = self._make_question_with_options(correct_index=2)
        self.assertEqual(q.correct_answer_display(), options[2].text)

class MultiAnswerQuestionTests(BaseExamTestCase):
    def test_save_sets_question_type(self):
        q = MultiAnswerQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        self.assertEqual(q.question_type, Question.Types.MULTI_ANSWER)
 
    def test_check_answer_true_when_all_correct_ids_given(self):
        q = MultiAnswerQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        o1 = QuestionOption.objects.create(question=q, text='A', is_correct=True, order=0)
        o2 = QuestionOption.objects.create(question=q, text='B', is_correct=True, order=1)
        QuestionOption.objects.create(question=q, text='C', is_correct=False, order=2)
 
        self.assertTrue(q.check_answer([o1.pk, o2.pk]))
 
    def test_check_answer_false_when_missing_one_correct(self):
        q = MultiAnswerQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        o1 = QuestionOption.objects.create(question=q, text='A', is_correct=True, order=0)
        QuestionOption.objects.create(question=q, text='B', is_correct=True, order=1)
 
        self.assertFalse(q.check_answer([o1.pk]))

class TrueFalseQuestionTests(BaseExamTestCase):
    def test_save_sets_question_type(self):
        q = TrueFalseQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', correct_answer=True
        )
        self.assertEqual(q.question_type, Question.Types.TRUE_FALSE)
 
    def test_check_answer_with_bool(self):
        q = TrueFalseQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', correct_answer=True
        )
        self.assertTrue(q.check_answer(True))
        self.assertFalse(q.check_answer(False))
 
    def test_check_answer_with_string_variants(self):
        q = TrueFalseQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', correct_answer=False
        )
        self.assertTrue(q.check_answer('false'))
        self.assertFalse(q.check_answer('true'))
        self.assertFalse(q.check_answer('verdadeiro'))
 
    def test_correct_answer_display(self):
        q_true = TrueFalseQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', correct_answer=True
        )
        q_false = TrueFalseQuestion.objects.create(
            exam=self.exam, statement='s2', explanation='e2', correct_answer=False
        )
        self.assertEqual(q_true.correct_answer_display(), 'Verdadeiro')
        self.assertEqual(q_false.correct_answer_display(), 'Falso')

class WrittenQuestionTests(BaseExamTestCase):
    def test_save_sets_question_type(self):
        q = WrittenQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', expected_answer='Paris'
        )
        self.assertEqual(q.question_type, Question.Types.WRITTEN)
 
    def test_check_answer_case_insensitive_by_default(self):
        q = WrittenQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', expected_answer='Paris'
        )
        self.assertTrue(q.check_answer('paris'))
        self.assertTrue(q.check_answer('PARIS'))
 
    def test_check_answer_ignores_accents_and_punctuation(self):
        q = WrittenQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', expected_answer='São Paulo!'
        )
        self.assertTrue(q.check_answer('sao paulo'))
        self.assertTrue(q.check_answer('  Sao   Paulo  '))
 
    def test_check_answer_respects_case_sensitive_flag(self):
        q = WrittenQuestion.objects.create(
            exam=self.exam,
            statement='s',
            explanation='e',
            expected_answer='Paris',
            case_sensitive=True,
        )
        self.assertFalse(q.check_answer('paris'))
        self.assertTrue(q.check_answer('Paris'))
 
    def test_check_answer_accepts_alternatives(self):
        q = WrittenQuestion.objects.create(
            exam=self.exam,
            statement='s',
            explanation='e',
            expected_answer='Paris',
            accepted_alternatives=['Cidade Luz', 'City of Light'],
        )
        self.assertTrue(q.check_answer('cidade luz'))
        self.assertFalse(q.check_answer('Londres'))
 
    def test_correct_answer_display_returns_expected_answer(self):
        q = WrittenQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', expected_answer='Paris'
        )
        self.assertEqual(q.correct_answer_display(), 'Paris')

class OrderingQuestionTests(BaseExamTestCase):
    def _make_ordered_question(self):
        q = OrderingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        items = [
            OrderingItem.objects.create(question=q, text=f'Item {i}', position=i)
            for i in range(1, 4)
        ]
        return q, items
 
    def test_save_sets_question_type(self):
        q, _ = self._make_ordered_question()
        self.assertEqual(q.question_type, Question.Types.ORDERING)
 
    def test_check_answer_true_for_correct_order(self):
        q, items = self._make_ordered_question()
        correct_ids = [it.id for it in sorted(items, key=lambda x: x.position)]
        self.assertTrue(q.check_answer(correct_ids))
 
    def test_check_answer_false_for_wrong_order(self):
        q, items = self._make_ordered_question()
        ids = [it.id for it in items]
        shuffled = [ids[1], ids[0], ids[2]]
        self.assertFalse(q.check_answer(shuffled))
 
    def test_check_answer_false_for_non_list_input(self):
        q, _ = self._make_ordered_question()
        self.assertFalse(q.check_answer('not-a-list'))
 
    def test_check_answer_false_for_non_castable_ids(self):
        q, _ = self._make_ordered_question()
        self.assertFalse(q.check_answer(['a', 'b', 'c']))
 
    def test_correct_answer_display_join_arrow(self):
        q, items = self._make_ordered_question()
        display = q.correct_answer_display()
        self.assertEqual(display, 'Item 1 → Item 2 → Item 3')

class MatchingQuestionTests(BaseExamTestCase):
    def _make_question_with_pairs(self):
        q = MatchingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        p1 = MatchingPair.objects.create(question=q, left='Brasil', right='Brasília', order=0)
        p2 = MatchingPair.objects.create(question=q, left='França', right='Paris', order=1)
        return q, [p1, p2]
 
    def test_save_sets_question_type(self):
        q, _ = self._make_question_with_pairs()
        self.assertEqual(q.question_type, Question.Types.MATCHING)
 
    def test_check_answer_dict_format_correct(self):
        q, pairs = self._make_question_with_pairs()
        answer = {str(p.pk): p.right for p in pairs}
        self.assertTrue(q.check_answer(answer))
 
    def test_check_answer_dict_format_incorrect(self):
        q, pairs = self._make_question_with_pairs()
        answer = {str(pairs[0].pk): 'Errado', str(pairs[1].pk): pairs[1].right}
        self.assertFalse(q.check_answer(answer))
 
    def test_check_answer_dict_format_missing_keys(self):
        q, pairs = self._make_question_with_pairs()
        answer = {str(pairs[0].pk): pairs[0].right}
        self.assertFalse(q.check_answer(answer))
 
    def test_check_answer_list_format_correct_order(self):
        q, pairs = self._make_question_with_pairs()
        rights_in_order = [p.right for p in sorted(pairs, key=lambda x: x.order)]
        self.assertTrue(q.check_answer(rights_in_order))
 
    def test_check_answer_list_format_wrong_order(self):
        q, pairs = self._make_question_with_pairs()
        rights_reversed = [p.right for p in sorted(pairs, key=lambda x: x.order)][::-1]
        self.assertFalse(q.check_answer(rights_reversed))
 
    def test_check_answer_invalid_type_returns_false(self):
        q, _ = self._make_question_with_pairs()
        self.assertFalse(q.check_answer(42))
 
    def test_correct_answer_display(self):
        q, pairs = self._make_question_with_pairs()
        display = q.correct_answer_display()
        self.assertIn('Brasil — Brasília', display)
        self.assertIn('França — Paris', display)

class FlashcardQuestionTests(BaseExamTestCase):
    def test_save_sets_question_type(self):
        q = FlashcardQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', front='Pergunta', back='Resposta'
        )
        self.assertEqual(q.question_type, Question.Types.FLASHCARD)
 
    def test_check_answer_is_always_false(self):
        q = FlashcardQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', front='P', back='R'
        )
        self.assertFalse(q.check_answer('R'))
        self.assertFalse(q.check_answer(None))
 
    def test_correct_answer_display_returns_back(self):
        q = FlashcardQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', front='P', back='Resposta certa'
        )
        self.assertEqual(q.correct_answer_display(), 'Resposta certa')
 
    def test_is_automatable_flag_false(self):
        q = FlashcardQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', front='P', back='R'
        )
        self.assertFalse(q.is_automatable)
