"""
Testes unitários para exams/question_types/*

Cobre cada handler de tipo de questão isoladamente:
- validate() (regras específicas do tipo)
- build_instance() (criação da instância polimórfica)
- save_dependencies() / update_dependencies() (registros relacionados)
- build_edit_json() (serialização para o editor)

Também cobre os utilitários genéricos usados pelos handlers de alternativas
(option_utils) e o registro central (question_types/__init__.py).
"""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from categories.models import Category
from exams.models import (
    Exam, Question, QuestionOption,
    MultipleChoiceQuestion, MultiAnswerQuestion,
    TrueFalseQuestion, WrittenQuestion,
    OrderingQuestion, OrderingItem,
    MatchingQuestion, MatchingPair,
    FlashcardQuestion,
)
from exams.question_types import get_handler, is_registered_type, QUESTION_TYPE_HANDLERS
from exams.question_types.option_utils import normalize_options, MAX_OPTIONS
from exams.question_types.text_utils import clean_text
from .test_support import make_querydict


class QuestionTypeTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='qt', password='pass12345')
        self.category = Category.objects.create(user=self.user, name='Cat')
        self.exam = Exam.objects.create(user=self.user, category=self.category, name='Prova QT')


# ── Registro central ──
class HandlerRegistryTests(TestCase):
    def test_all_question_types_have_a_handler(self):
        for type_value, _ in Question.Types.choices:
            self.assertTrue(is_registered_type(type_value))

    def test_get_handler_returns_matching_type_value(self):
        for type_value in QUESTION_TYPE_HANDLERS:
            self.assertEqual(get_handler(type_value).type_value, type_value)

    def test_get_handler_raises_for_unknown_type(self):
        with self.assertRaises(ValueError):
            get_handler('tipo_invalido')

    def test_is_registered_type_false_for_unknown(self):
        self.assertFalse(is_registered_type('tipo_invalido'))
        self.assertFalse(is_registered_type(None))


# ── Utilitários genéricos (text_utils / option_utils) ──
class TextAndOptionUtilsTests(TestCase):
    def test_clean_text_strips_and_handles_none(self):
        self.assertEqual(clean_text('  olá  '), 'olá')
        self.assertEqual(clean_text(None), '')

    def test_normalize_options_strips_blanks(self):
        qd = make_querydict({'data_options': ['A', '  ', 'B', '']})
        self.assertEqual(normalize_options(qd), ['A', 'B'])

    def test_normalize_options_raises_above_max(self):
        qd = make_querydict({'data_options': [f'Opt{i}' for i in range(MAX_OPTIONS + 1)]})
        with self.assertRaises(ValidationError):
            normalize_options(qd)

    def test_normalize_options_allows_exactly_max(self):
        qd = make_querydict({'data_options': [f'Opt{i}' for i in range(MAX_OPTIONS)]})
        self.assertEqual(len(normalize_options(qd)), MAX_OPTIONS)


# ── Múltipla escolha / Resposta múltipla (ChoiceQuestionHandler) ──
class ChoiceHandlerTestsMixin:
    """Mixin parametrizado por type_value/model_class/multiple_correct,
    reaproveitado pelos dois testes concretos abaixo (DRY: mesma bateria
    de casos para multiple_choice e multi_answer, que só diferem em
    quantas alternativas podem ser marcadas como corretas)."""

    def correct_field(self, indices):
        indices_list = list(indices)
        return {'data_correct': [str(i) for i in indices_list]} if self.multiple_correct \
            else {'data_correct': str(indices_list[0])}

    def test_validate_requires_at_least_two_options(self):
        qd = make_querydict({'data_options': ['Única'], **self.correct_field([0])})
        errors = []
        self.handler.validate(qd, errors)
        self.assertTrue(any('pelo menos 2' in e for e in errors))

    def test_validate_requires_correct_marked(self):
        qd = make_querydict({'data_options': ['A', 'B']})
        errors = []
        self.handler.validate(qd, errors)
        self.assertTrue(errors)

    def test_validate_rejects_option_over_limit(self):
        qd = make_querydict({'data_options': ['A' * 501, 'B'], **self.correct_field([0])})
        errors = []
        self.handler.validate(qd, errors)
        self.assertTrue(any('500 caracteres' in e for e in errors))

    def test_validate_accepts_option_at_limit(self):
        qd = make_querydict({'data_options': ['A' * 500, 'B'], **self.correct_field([0])})
        errors = []
        self.handler.validate(qd, errors)
        self.assertEqual(errors, [])

    def test_save_dependencies_creates_options_with_correct_flags(self):
        question = self.model_class.objects.create(exam=self.exam, statement='s', explanation='e')
        qd = make_querydict({'data_options': ['A', 'B', 'C'], **self.correct_field(self.correct_indices)})
        self.handler.save_dependencies(question, qd)

        options = list(question.options.order_by('order'))
        self.assertEqual([o.text for o in options], ['A', 'B', 'C'])
        for i, opt in enumerate(options):
            self.assertEqual(opt.is_correct, i in self.correct_indices)

    def test_update_dependencies_reuses_existing_and_trims_extra(self):
        question = self.model_class.objects.create(exam=self.exam, statement='s', explanation='e')
        for i, text in enumerate(['A', 'B', 'C']):
            QuestionOption.objects.create(question=question, text=text, is_correct=(i == 0), order=i)

        qd = make_querydict({'data_options': ['X', 'Y'], **self.correct_field([1])})
        self.handler.update_dependencies(question, qd)

        options = list(question.options.order_by('order'))
        self.assertEqual([o.text for o in options], ['X', 'Y'])
        self.assertFalse(options[0].is_correct)
        self.assertTrue(options[1].is_correct)

    def test_update_dependencies_adds_new_options(self):
        question = self.model_class.objects.create(exam=self.exam, statement='s', explanation='e')
        QuestionOption.objects.create(question=question, text='A', is_correct=True, order=0)

        qd = make_querydict({'data_options': ['A', 'B', 'C'], **self.correct_field([2])})
        self.handler.update_dependencies(question, qd)

        self.assertEqual(question.options.count(), 3)
        self.assertTrue(question.options.order_by('order')[2].is_correct)

    def test_update_dependencies_raises_below_minimum(self):
        question = self.model_class.objects.create(exam=self.exam, statement='s', explanation='e')
        qd = make_querydict({'data_options': ['Única'], **self.correct_field([0])})
        with self.assertRaises(ValidationError):
            self.handler.update_dependencies(question, qd)

    def test_build_edit_json_reflects_correct_options(self):
        question = self.model_class.objects.create(exam=self.exam, statement='s', explanation='e')
        for i, text in enumerate(['A', 'B']):
            QuestionOption.objects.create(question=question, text=text, is_correct=(i in self.correct_indices), order=i)

        data = self.handler.build_edit_json(question)
        self.assertEqual(data['options'], ['A', 'B'])


class MultipleChoiceHandlerTests(ChoiceHandlerTestsMixin, QuestionTypeTestCase):
    def setUp(self):
        super().setUp()
        self.handler = get_handler(Question.Types.MULTIPLE_CHOICE)
        self.model_class = MultipleChoiceQuestion
        self.multiple_correct = False
        self.correct_indices = {1}

    def test_build_edit_json_correct_is_single_index(self):
        question = MultipleChoiceQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        QuestionOption.objects.create(question=question, text='A', is_correct=False, order=0)
        QuestionOption.objects.create(question=question, text='B', is_correct=True, order=1)
        self.assertEqual(self.handler.build_edit_json(question)['correct'], 1)


class MultiAnswerHandlerTests(ChoiceHandlerTestsMixin, QuestionTypeTestCase):
    def setUp(self):
        super().setUp()
        self.handler = get_handler(Question.Types.MULTI_ANSWER)
        self.model_class = MultiAnswerQuestion
        self.multiple_correct = True
        self.correct_indices = {0, 2}

    def test_build_edit_json_correct_is_index_list(self):
        question = MultiAnswerQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        QuestionOption.objects.create(question=question, text='A', is_correct=True, order=0)
        QuestionOption.objects.create(question=question, text='B', is_correct=True, order=1)
        QuestionOption.objects.create(question=question, text='C', is_correct=False, order=2)
        self.assertEqual(self.handler.build_edit_json(question)['correct'], [0, 1])


# ── Verdadeiro ou falso ──
class TrueFalseHandlerTests(QuestionTypeTestCase):
    def setUp(self):
        super().setUp()
        self.handler = get_handler(Question.Types.TRUE_FALSE)

    def test_validate_rejects_invalid_value(self):
        errors = []
        self.handler.validate(make_querydict({'data_correct': 'talvez'}), errors)
        self.assertTrue(errors)

    def test_validate_accepts_valid_values(self):
        for value in ('true', 'false', '1', '0', 'verdadeiro', 'falso'):
            errors = []
            self.handler.validate(make_querydict({'data_correct': value}), errors)
            self.assertEqual(errors, [], value)

    def test_build_instance_reads_correct_flag(self):
        instance = self.handler.build_instance('s', 'e', make_querydict({'data_correct': 'true'}))
        self.assertTrue(instance.correct_answer)

    def test_update_dependencies_flips_value(self):
        question = TrueFalseQuestion.objects.create(exam=self.exam, statement='s', explanation='e', correct_answer=False)
        self.handler.update_dependencies(question, make_querydict({'data_correct': 'true'}))
        question.refresh_from_db()
        self.assertTrue(question.truefalsequestion.correct_answer)

    def test_update_dependencies_raises_for_invalid_value(self):
        question = TrueFalseQuestion.objects.create(exam=self.exam, statement='s', explanation='e', correct_answer=False)
        with self.assertRaises(ValidationError):
            self.handler.update_dependencies(question, make_querydict({'data_correct': 'invalido'}))

    def test_build_edit_json(self):
        question = TrueFalseQuestion.objects.create(exam=self.exam, statement='s', explanation='e', correct_answer=True)
        self.assertEqual(self.handler.build_edit_json(question), {'correct': True})


# ── Resposta escrita ──
class WrittenHandlerTests(QuestionTypeTestCase):
    def setUp(self):
        super().setUp()
        self.handler = get_handler(Question.Types.WRITTEN)

    def test_validate_rejects_empty_answer(self):
        errors = []
        self.handler.validate(make_querydict({'data_answer': ''}), errors)
        self.assertTrue(errors)

    def test_validate_rejects_answer_over_limit(self):
        errors = []
        self.handler.validate(make_querydict({'data_answer': 'A' * 256}), errors)
        self.assertTrue(any('255 caracteres' in e for e in errors))

    def test_validate_accepts_answer_at_limit(self):
        errors = []
        self.handler.validate(make_querydict({'data_answer': 'A' * 255}), errors)
        self.assertEqual(errors, [])

    def test_build_instance_reads_and_trims_answer(self):
        instance = self.handler.build_instance('s', 'e', make_querydict({'data_answer': ' Paris '}))
        self.assertEqual(instance.expected_answer, 'Paris')

    def test_update_dependencies_updates_answer(self):
        question = WrittenQuestion.objects.create(exam=self.exam, statement='s', explanation='e', expected_answer='Antigo')
        self.handler.update_dependencies(question, make_querydict({'data_answer': 'Novo'}))
        question.refresh_from_db()
        self.assertEqual(question.writtenquestion.expected_answer, 'Novo')

    def test_update_dependencies_raises_when_empty(self):
        question = WrittenQuestion.objects.create(exam=self.exam, statement='s', explanation='e', expected_answer='Antigo')
        with self.assertRaises(ValidationError):
            self.handler.update_dependencies(question, make_querydict({'data_answer': ''}))

    def test_build_edit_json(self):
        question = WrittenQuestion.objects.create(exam=self.exam, statement='s', explanation='e', expected_answer='Paris')
        self.assertEqual(self.handler.build_edit_json(question), {'answer': 'Paris'})


# ── Ordenar elementos ──
class OrderingHandlerTests(QuestionTypeTestCase):
    def setUp(self):
        super().setUp()
        self.handler = get_handler(Question.Types.ORDERING)

    def test_validate_requires_at_least_two_items(self):
        errors = []
        self.handler.validate(make_querydict({'data_items': ['Único']}), errors)
        self.assertTrue(errors)

    def test_validate_rejects_item_over_limit(self):
        errors = []
        self.handler.validate(make_querydict({'data_items': ['Ok', 'X' * 501]}), errors)
        self.assertTrue(any('500 caracteres' in e for e in errors))

    def test_save_dependencies_creates_items_in_order(self):
        question = OrderingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        self.handler.save_dependencies(question, make_querydict({'data_items': ['Primeiro', 'Segundo', 'Terceiro']}))
        items = list(question.items.order_by('position'))
        self.assertEqual([i.text for i in items], ['Primeiro', 'Segundo', 'Terceiro'])
        self.assertEqual([i.position for i in items], [1, 2, 3])

    def test_save_dependencies_raises_below_minimum(self):
        question = OrderingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        with self.assertRaises(ValidationError):
            self.handler.save_dependencies(question, make_querydict({'data_items': ['Único']}))

    def test_update_dependencies_replaces_items(self):
        question = OrderingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        OrderingItem.objects.create(question=question, text='Velho1', position=1)
        OrderingItem.objects.create(question=question, text='Velho2', position=2)

        self.handler.update_dependencies(question, make_querydict({'data_items': ['Novo1', 'Novo2', 'Novo3']}))

        items = list(question.items.order_by('position'))
        self.assertEqual([i.text for i in items], ['Novo1', 'Novo2', 'Novo3'])

    def test_build_edit_json(self):
        question = OrderingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        OrderingItem.objects.create(question=question, text='Um', position=1)
        OrderingItem.objects.create(question=question, text='Dois', position=2)
        self.assertEqual(self.handler.build_edit_json(question), {'items': ['Um', 'Dois']})


# ── Relacionar colunas ──
class MatchingHandlerTests(QuestionTypeTestCase):
    def setUp(self):
        super().setUp()
        self.handler = get_handler(Question.Types.MATCHING)

    def test_validate_requires_balanced_and_filled_columns(self):
        errors = []
        self.handler.validate(make_querydict({'data_pairs_left': ['A', 'B'], 'data_pairs_right': ['1']}), errors)
        self.assertTrue(errors)

    def test_validate_rejects_pair_over_limit(self):
        errors = []
        self.handler.validate(
            make_querydict({'data_pairs_left': ['A', 'Y' * 501], 'data_pairs_right': ['1', '2']}), errors
        )
        self.assertTrue(any('500 caracteres' in e for e in errors))

    def test_save_dependencies_creates_pairs_in_order(self):
        question = MatchingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        self.handler.save_dependencies(question, make_querydict({
            'data_pairs_left': ['Brasil', 'França'], 'data_pairs_right': ['Brasília', 'Paris'],
        }))
        pairs = list(question.pairs.order_by('order'))
        self.assertEqual(pairs[0].left, 'Brasil')
        self.assertEqual(pairs[1].right, 'Paris')

    def test_save_dependencies_raises_when_mismatched(self):
        question = MatchingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        with self.assertRaises(ValidationError):
            self.handler.save_dependencies(question, make_querydict({
                'data_pairs_left': ['A', 'B'], 'data_pairs_right': ['1'],
            }))

    def test_update_dependencies_replaces_pairs(self):
        question = MatchingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        MatchingPair.objects.create(question=question, left='A', right='1', order=0)

        self.handler.update_dependencies(question, make_querydict({
            'data_pairs_left': ['X', 'Y'], 'data_pairs_right': ['1', '2'],
        }))

        pairs = list(question.pairs.order_by('order'))
        self.assertEqual([p.left for p in pairs], ['X', 'Y'])

    def test_build_edit_json(self):
        question = MatchingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        MatchingPair.objects.create(question=question, left='A', right='1', order=0)
        self.assertEqual(self.handler.build_edit_json(question), {'pairs': [{'left': 'A', 'right': '1'}]})


# ── Flashcard ──
class FlashcardHandlerTests(QuestionTypeTestCase):
    def setUp(self):
        super().setUp()
        self.handler = get_handler(Question.Types.FLASHCARD)

    def test_validate_requires_front_and_back(self):
        errors = []
        self.handler.validate(make_querydict({'data_front': 'Frente', 'data_back': ''}), errors)
        self.assertTrue(errors)

    def test_validate_rejects_text_over_limit(self):
        errors = []
        self.handler.validate(make_querydict({'data_front': 'F' * 1001, 'data_back': 'Verso'}), errors)
        self.assertTrue(any('máximo' in e for e in errors))

    def test_build_instance_reads_front_and_back(self):
        instance = self.handler.build_instance('s', 'e', make_querydict({'data_front': ' P ', 'data_back': ' R '}))
        self.assertEqual(instance.front, 'P')
        self.assertEqual(instance.back, 'R')

    def test_update_dependencies_updates_texts(self):
        question = FlashcardQuestion.objects.create(exam=self.exam, statement='s', explanation='e', front='F', back='B')
        self.handler.update_dependencies(question, make_querydict({'data_front': 'Novo F', 'data_back': 'Novo B'}))
        question.refresh_from_db()
        self.assertEqual(question.flashcardquestion.front, 'Novo F')
        self.assertEqual(question.flashcardquestion.back, 'Novo B')

    def test_update_dependencies_raises_when_empty(self):
        question = FlashcardQuestion.objects.create(exam=self.exam, statement='s', explanation='e', front='F', back='B')
        with self.assertRaises(ValidationError):
            self.handler.update_dependencies(question, make_querydict({'data_front': '', 'data_back': 'x'}))

    def test_build_edit_json(self):
        question = FlashcardQuestion.objects.create(exam=self.exam, statement='s', explanation='e', front='F', back='B')
        self.assertEqual(self.handler.build_edit_json(question), {'front': 'F', 'back': 'B'})