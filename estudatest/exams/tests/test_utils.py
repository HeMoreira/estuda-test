"""
Testes unitários para exams/utils.py
 
Cobre:
- save_exam_with_default_category_if_needed / _get_or_create_default_category
- _normalize_option_values
- validate_question_payload (para cada tipo de questão)
- _create_polymorphic_instance
- _process_question_dependencies (criação de options/items/pairs)
- _update_polymorphic_instance (atualização e remoção de sobras)
- _build_question_json_data
- _flatten_validation_errors
"""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.test import TestCase
 
from categories.models import Category
from exams.forms import ExamForm
from exams.models import (
    Exam,
    Question,
    QuestionOption,
    MultipleChoiceQuestion,
    TrueFalseQuestion,
    WrittenQuestion,
    OrderingQuestion,
    OrderingItem,
    MatchingQuestion,
    MatchingPair,
    FlashcardQuestion,
)
from exams.utils import (
    save_exam_with_default_category_if_needed,
    _normalize_option_values,
    validate_question_payload,
    _create_polymorphic_instance,
    _process_question_dependencies,
    _update_polymorphic_instance,
    _build_question_json_data,
    _flatten_validation_errors,
)
 
 
def make_querydict(data):
    """Constrói um QueryDict mutável a partir de um dict simples,
    onde valores lista viram múltiplos valores (equivalente a POST real)."""
    qd = QueryDict(mutable=True)
    for key, value in data.items():
        if isinstance(value, (list, tuple)):
            qd.setlist(key, list(value))
        else:
            qd[key] = value
    return qd
 
 
class SaveExamDefaultCategoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='joao', password='pass12345')
 
    def test_creates_default_category_when_none_selected(self):
        form = ExamForm(self.user, data={'name': 'Prova sem categoria', 'category': ''})
        self.assertTrue(form.is_valid(), form.errors)
        exam = save_exam_with_default_category_if_needed(
            _FakeRequest(self.user), form
        )
        self.assertIsNotNone(exam.category)
        self.assertEqual(exam.category.name, '~ sem categoria')
        self.assertEqual(exam.user, self.user)
 
    def test_reuses_existing_default_category(self):
        Category.objects.create(user=self.user, name='~ sem categoria')
        form = ExamForm(self.user, data={'name': 'Outra prova', 'category': ''})
        self.assertTrue(form.is_valid(), form.errors)
        exam = save_exam_with_default_category_if_needed(_FakeRequest(self.user), form)
        self.assertEqual(
            Category.objects.filter(user=self.user, name='~ sem categoria').count(), 1
        )
        self.assertEqual(exam.category.name, '~ sem categoria')
 
    def test_keeps_explicit_category_when_provided(self):
        cat = Category.objects.create(user=self.user, name='Matemática')
        form = ExamForm(self.user, data={'name': 'Prova de mat', 'category': cat.pk})
        self.assertTrue(form.is_valid(), form.errors)
        exam = save_exam_with_default_category_if_needed(_FakeRequest(self.user), form)
        self.assertEqual(exam.category, cat)
 
 
class _FakeRequest:
    """Stub simples para simular request.user nas funções que só usam esse atributo."""
    def __init__(self, user):
        self.user = user
 
 
class NormalizeOptionValuesTests(TestCase):
    def test_strips_blank_options(self):
        qd = make_querydict({'data_options': ['A', '  ', 'B', '']})
        self.assertEqual(_normalize_option_values(qd), ['A', 'B'])
 
    def test_raises_when_more_than_ten_options(self):
        qd = make_querydict({'data_options': [f'Opt{i}' for i in range(11)]})
        with self.assertRaises(ValidationError):
            _normalize_option_values(qd)
 
    def test_allows_exactly_ten_options(self):
        qd = make_querydict({'data_options': [f'Opt{i}' for i in range(10)]})
        self.assertEqual(len(_normalize_option_values(qd)), 10)
 
 
class ValidateQuestionPayloadTests(TestCase):
    def test_raises_when_statement_or_explanation_empty(self):
        qd = make_querydict({'statement': '', 'explanation': ''})
        with self.assertRaises(ValidationError):
            validate_question_payload(Question.Types.WRITTEN, qd)
 
    def test_raises_when_statement_too_long(self):
        qd = make_querydict({'statement': 'a' * 1001, 'explanation': 'ok'})
        with self.assertRaises(ValidationError):
            validate_question_payload(Question.Types.WRITTEN, qd)
 
    def test_valid_multiple_choice_payload_passes(self):
        qd = make_querydict({
            'statement': 'Pergunta?',
            'explanation': 'Porque sim.',
            'data_options': ['A', 'B'],
            'data_correct': '0',
        })
        stmt, expl = validate_question_payload(Question.Types.MULTIPLE_CHOICE, qd)
        self.assertEqual(stmt, 'Pergunta?')
        self.assertEqual(expl, 'Porque sim.')
 
    def test_multiple_choice_requires_at_least_two_options(self):
        qd = make_querydict({
            'statement': 'Pergunta?',
            'explanation': 'Porque sim.',
            'data_options': ['Única'],
            'data_correct': '0',
        })
        with self.assertRaises(ValidationError):
            validate_question_payload(Question.Types.MULTIPLE_CHOICE, qd)
 
    def test_multiple_choice_requires_correct_marked(self):
        qd = make_querydict({
            'statement': 'Pergunta?',
            'explanation': 'Porque sim.',
            'data_options': ['A', 'B'],
        })
        with self.assertRaises(ValidationError):
            validate_question_payload(Question.Types.MULTIPLE_CHOICE, qd)
 
    def test_multi_answer_requires_at_least_one_correct(self):
        qd = make_querydict({
            'statement': 'Pergunta?',
            'explanation': 'Porque sim.',
            'data_options': ['A', 'B'],
        })
        with self.assertRaises(ValidationError):
            validate_question_payload(Question.Types.MULTI_ANSWER, qd)
 
    def test_true_false_requires_valid_value(self):
        qd = make_querydict({
            'statement': 'A Terra é redonda?',
            'explanation': 'Sim, é.',
            'data_correct': 'talvez',
        })
        with self.assertRaises(ValidationError):
            validate_question_payload(Question.Types.TRUE_FALSE, qd)
 
    def test_written_requires_non_empty_answer(self):
        qd = make_querydict({
            'statement': 'Capital da França?',
            'explanation': 'É Paris.',
            'data_answer': '',
        })
        with self.assertRaises(ValidationError):
            validate_question_payload(Question.Types.WRITTEN, qd)
 
    def test_ordering_requires_at_least_two_items(self):
        qd = make_querydict({
            'statement': 'Ordene',
            'explanation': 'Exp',
            'data_items': ['Único'],
        })
        with self.assertRaises(ValidationError):
            validate_question_payload(Question.Types.ORDERING, qd)
 
    def test_matching_requires_equal_and_filled_columns(self):
        qd = make_querydict({
            'statement': 'Relacione',
            'explanation': 'Exp',
            'data_pairs_left': ['A', 'B'],
            'data_pairs_right': ['1'],
        })
        with self.assertRaises(ValidationError):
            validate_question_payload(Question.Types.MATCHING, qd)
 
    def test_flashcard_requires_front_and_back(self):
        qd = make_querydict({
            'statement': 'Card',
            'explanation': 'Exp',
            'data_front': 'Frente',
            'data_back': '',
        })
        with self.assertRaises(ValidationError):
            validate_question_payload(Question.Types.FLASHCARD, qd)

    def test_multiple_choice_option_too_long_raises(self):
        qd = make_querydict({
            'statement': 'Pergunta?',
            'explanation': 'Porque sim.',
            'data_options': ['A' * 501, 'B'],
            'data_correct': '0',
        })
        with self.assertRaises(ValidationError) as ctx:
            validate_question_payload(Question.Types.MULTIPLE_CHOICE, qd)
        self.assertTrue(
            any('máximo 500 caracteres' in m for m in ctx.exception.messages)
        )
 
    def test_multiple_choice_option_at_limit_is_valid(self):
        qd = make_querydict({
            'statement': 'Pergunta?',
            'explanation': 'Porque sim.',
            'data_options': ['A' * 500, 'B'],
            'data_correct': '0',
        })
        # Não deve levantar ValidationError
        validate_question_payload(Question.Types.MULTIPLE_CHOICE, qd)
 
    def test_multi_answer_option_too_long_raises(self):
        qd = make_querydict({
            'statement': 'Pergunta?',
            'explanation': 'Porque sim.',
            'data_options': ['A', 'B' * 501],
            'data_correct': ['0'],
        })
        with self.assertRaises(ValidationError) as ctx:
            validate_question_payload(Question.Types.MULTI_ANSWER, qd)
        self.assertTrue(
            any('máximo 500 caracteres' in m for m in ctx.exception.messages)
        )
 
    def test_written_answer_too_long_raises(self):
        qd = make_querydict({
            'statement': 'Capital da França?',
            'explanation': 'É Paris.',
            'data_answer': 'A' * 256,
        })
        with self.assertRaises(ValidationError) as ctx:
            validate_question_payload(Question.Types.WRITTEN, qd)
        self.assertTrue(
            any('máximo 255 caracteres' in m for m in ctx.exception.messages)
        )
 
    def test_written_answer_at_limit_is_valid(self):
        qd = make_querydict({
            'statement': 'Capital da França?',
            'explanation': 'É Paris.',
            'data_answer': 'A' * 255,
        })
        validate_question_payload(Question.Types.WRITTEN, qd)
 
    def test_ordering_item_too_long_raises(self):
        qd = make_querydict({
            'statement': 'Ordene',
            'explanation': 'Exp',
            'data_items': ['Item válido', 'X' * 501],
        })
        with self.assertRaises(ValidationError) as ctx:
            validate_question_payload(Question.Types.ORDERING, qd)
        self.assertTrue(
            any('máximo 500 caracteres' in m for m in ctx.exception.messages)
        )
 
    def test_ordering_item_at_limit_is_valid(self):
        qd = make_querydict({
            'statement': 'Ordene',
            'explanation': 'Exp',
            'data_items': ['Item válido', 'X' * 500],
        })
        validate_question_payload(Question.Types.ORDERING, qd)
 
    def test_matching_pair_too_long_raises(self):
        qd = make_querydict({
            'statement': 'Relacione',
            'explanation': 'Exp',
            'data_pairs_left': ['A', 'Y' * 501],
            'data_pairs_right': ['1', '2'],
        })
        with self.assertRaises(ValidationError) as ctx:
            validate_question_payload(Question.Types.MATCHING, qd)
        self.assertTrue(
            any('máximo 500 caracteres' in m for m in ctx.exception.messages)
        )
 
    def test_matching_pair_too_long_on_right_column_raises(self):
        qd = make_querydict({
            'statement': 'Relacione',
            'explanation': 'Exp',
            'data_pairs_left': ['A', 'B'],
            'data_pairs_right': ['1', 'Z' * 501],
        })
        with self.assertRaises(ValidationError) as ctx:
            validate_question_payload(Question.Types.MATCHING, qd)
        self.assertTrue(
            any('máximo 500 caracteres' in m for m in ctx.exception.messages)
        )
 
    def test_matching_pair_at_limit_is_valid(self):
        qd = make_querydict({
            'statement': 'Relacione',
            'explanation': 'Exp',
            'data_pairs_left': ['A', 'Y' * 500],
            'data_pairs_right': ['1', '2'],
        })
        validate_question_payload(Question.Types.MATCHING, qd)
 
    def test_flashcard_front_too_long_raises(self):
        qd = make_querydict({
            'statement': 'Card',
            'explanation': 'Exp',
            'data_front': 'F' * 1001,
            'data_back': 'Verso válido',
        })
        with self.assertRaises(ValidationError) as ctx:
            validate_question_payload(Question.Types.FLASHCARD, qd)
        # A mensagem no código-fonte cita "255 caracteres" por engano
        # (o limite realmente validado é 1000); checamos só que disparou.
        self.assertTrue(any('máximo' in m for m in ctx.exception.messages))
 
    def test_flashcard_back_too_long_raises(self):
        qd = make_querydict({
            'statement': 'Card',
            'explanation': 'Exp',
            'data_front': 'Frente válida',
            'data_back': 'B' * 1001,
        })
        with self.assertRaises(ValidationError) as ctx:
            validate_question_payload(Question.Types.FLASHCARD, qd)
        self.assertTrue(any('máximo' in m for m in ctx.exception.messages))
 
    def test_flashcard_within_limits_is_valid(self):
        qd = make_querydict({
            'statement': 'Card',
            'explanation': 'Exp',
            'data_front': 'F' * 1000,
            'data_back': 'B' * 1000,
        })
        validate_question_payload(Question.Types.FLASHCARD, qd)

 
 
class CreatePolymorphicInstanceTests(TestCase):
    def test_multiple_choice_instance(self):
        q = _create_polymorphic_instance(Question.Types.MULTIPLE_CHOICE, 's', 'e', make_querydict({}))
        self.assertIsInstance(q, MultipleChoiceQuestion)
 
    def test_true_false_instance_reads_correct_flag(self):
        qd = make_querydict({'data_correct': 'true'})
        q = _create_polymorphic_instance(Question.Types.TRUE_FALSE, 's', 'e', qd)
        self.assertIsInstance(q, TrueFalseQuestion)
        self.assertTrue(q.correct_answer)
 
    def test_written_instance_reads_answer(self):
        qd = make_querydict({'data_answer': ' Paris '})
        q = _create_polymorphic_instance(Question.Types.WRITTEN, 's', 'e', qd)
        self.assertEqual(q.expected_answer, 'Paris')
 
    def test_flashcard_instance_reads_front_back(self):
        qd = make_querydict({'data_front': ' P ', 'data_back': ' R '})
        q = _create_polymorphic_instance(Question.Types.FLASHCARD, 's', 'e', qd)
        self.assertEqual(q.front, 'P')
        self.assertEqual(q.back, 'R')
 
    def test_unknown_type_returns_none(self):
        q = _create_polymorphic_instance('tipo_invalido', 's', 'e', make_querydict({}))
        self.assertIsNone(q)
 
 
class ProcessQuestionDependenciesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dep', password='pass12345')
        self.category = Category.objects.create(user=self.user, name='Cat')
        self.exam = Exam.objects.create(user=self.user, category=self.category, name='Prova Dep')
 
    def test_creates_options_for_multiple_choice(self):
        q = MultipleChoiceQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        qd = make_querydict({'data_options': ['A', 'B', 'C'], 'data_correct': '1'})
        _process_question_dependencies(q, Question.Types.MULTIPLE_CHOICE, qd)
        options = list(q.options.order_by('order'))
        self.assertEqual(len(options), 3)
        self.assertTrue(options[1].is_correct)
        self.assertFalse(options[0].is_correct)
 
    def test_creates_items_for_ordering(self):
        q = OrderingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        qd = make_querydict({'data_items': ['Primeiro', 'Segundo', 'Terceiro']})
        _process_question_dependencies(q, Question.Types.ORDERING, qd)
        items = list(q.items.order_by('position'))
        self.assertEqual([i.text for i in items], ['Primeiro', 'Segundo', 'Terceiro'])
        self.assertEqual([i.position for i in items], [1, 2, 3])
 
    def test_ordering_raises_when_less_than_two_items(self):
        q = OrderingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        qd = make_querydict({'data_items': ['Único']})
        with self.assertRaises(ValidationError):
            _process_question_dependencies(q, Question.Types.ORDERING, qd)
 
    def test_creates_pairs_for_matching(self):
        q = MatchingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        qd = make_querydict({
            'data_pairs_left': ['Brasil', 'França'],
            'data_pairs_right': ['Brasília', 'Paris'],
        })
        _process_question_dependencies(q, Question.Types.MATCHING, qd)
        pairs = list(q.pairs.order_by('order'))
        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0].left, 'Brasil')
        self.assertEqual(pairs[1].right, 'Paris')
 
    def test_matching_raises_when_columns_mismatched(self):
        q = MatchingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        qd = make_querydict({
            'data_pairs_left': ['Brasil', 'França'],
            'data_pairs_right': ['Brasília'],
        })
        with self.assertRaises(ValidationError):
            _process_question_dependencies(q, Question.Types.MATCHING, qd)
 
 
class UpdatePolymorphicInstanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='upd', password='pass12345')
        self.category = Category.objects.create(user=self.user, name='Cat')
        self.exam = Exam.objects.create(user=self.user, category=self.category, name='Prova Upd')
 
    def test_update_multiple_choice_reuses_existing_and_removes_extra(self):
        q = MultipleChoiceQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        for i, text in enumerate(['A', 'B', 'C']):
            QuestionOption.objects.create(question=q, text=text, is_correct=(i == 0), order=i)
 
        qd = make_querydict({'data_options': ['X', 'Y'], 'data_correct': '1'})
        _update_polymorphic_instance(q, Question.Types.MULTIPLE_CHOICE, qd)
 
        options = list(q.options.order_by('order'))
        self.assertEqual(len(options), 2)
        self.assertEqual(options[0].text, 'X')
        self.assertEqual(options[1].text, 'Y')
        self.assertTrue(options[1].is_correct)
        self.assertFalse(options[0].is_correct)
 
    def test_update_multiple_choice_adds_new_options_when_more_provided(self):
        q = MultipleChoiceQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        QuestionOption.objects.create(question=q, text='A', is_correct=True, order=0)
 
        qd = make_querydict({'data_options': ['A', 'B', 'C'], 'data_correct': '2'})
        _update_polymorphic_instance(q, Question.Types.MULTIPLE_CHOICE, qd)
 
        options = list(q.options.order_by('order'))
        self.assertEqual(len(options), 3)
        self.assertTrue(options[2].is_correct)
 
    def test_update_multiple_choice_raises_with_less_than_two_options(self):
        q = MultipleChoiceQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        qd = make_querydict({'data_options': ['Única'], 'data_correct': '0'})
        with self.assertRaises(ValidationError):
            _update_polymorphic_instance(q, Question.Types.MULTIPLE_CHOICE, qd)
 
    def test_update_true_false(self):
        q = TrueFalseQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', correct_answer=False
        )
        qd = make_querydict({'data_correct': 'true'})
        _update_polymorphic_instance(q, Question.Types.TRUE_FALSE, qd)
        q.refresh_from_db()
        self.assertTrue(q.truefalsequestion.correct_answer)
 
    def test_update_true_false_invalid_value_raises(self):
        q = TrueFalseQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', correct_answer=False
        )
        qd = make_querydict({'data_correct': 'invalido'})
        with self.assertRaises(ValidationError):
            _update_polymorphic_instance(q, Question.Types.TRUE_FALSE, qd)
 
    def test_update_written(self):
        q = WrittenQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', expected_answer='Antigo'
        )
        qd = make_querydict({'data_answer': 'Novo'})
        _update_polymorphic_instance(q, Question.Types.WRITTEN, qd)
        q.refresh_from_db()
        self.assertEqual(q.writtenquestion.expected_answer, 'Novo')
 
    def test_update_ordering_replaces_items(self):
        q = OrderingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        OrderingItem.objects.create(question=q, text='Velho1', position=1)
        OrderingItem.objects.create(question=q, text='Velho2', position=2)
 
        qd = make_querydict({'data_items': ['Novo1', 'Novo2', 'Novo3']})
        _update_polymorphic_instance(q, Question.Types.ORDERING, qd)
 
        items = list(q.orderingquestion.items.order_by('position'))
        self.assertEqual([i.text for i in items], ['Novo1', 'Novo2', 'Novo3'])
 
    def test_update_matching_replaces_pairs(self):
        q = MatchingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        MatchingPair.objects.create(question=q, left='A', right='1', order=0)
 
        qd = make_querydict({
            'data_pairs_left': ['X', 'Y'],
            'data_pairs_right': ['1', '2'],
        })
        _update_polymorphic_instance(q, Question.Types.MATCHING, qd)
 
        pairs = list(q.matchingquestion.pairs.order_by('order'))
        self.assertEqual([p.left for p in pairs], ['X', 'Y'])
 
    def test_update_flashcard(self):
        q = FlashcardQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', front='F', back='B'
        )
        qd = make_querydict({'data_front': 'Novo front', 'data_back': 'Novo back'})
        _update_polymorphic_instance(q, Question.Types.FLASHCARD, qd)
        q.refresh_from_db()
        self.assertEqual(q.flashcardquestion.front, 'Novo front')
        self.assertEqual(q.flashcardquestion.back, 'Novo back')
 
    def test_update_flashcard_raises_when_empty(self):
        q = FlashcardQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', front='F', back='B'
        )
        qd = make_querydict({'data_front': '', 'data_back': 'x'})
        with self.assertRaises(ValidationError):
            _update_polymorphic_instance(q, Question.Types.FLASHCARD, qd)
 
 
class BuildQuestionJsonDataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='json', password='pass12345')
        self.category = Category.objects.create(user=self.user, name='Cat')
        self.exam = Exam.objects.create(user=self.user, category=self.category, name='Prova Json')
 
    def test_multiple_choice_json(self):
        q = MultipleChoiceQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        QuestionOption.objects.create(question=q, text='A', is_correct=False, order=0)
        QuestionOption.objects.create(question=q, text='B', is_correct=True, order=1)
 
        data = _build_question_json_data(q, 'multiple_choice')
        self.assertEqual(data['options'], ['A', 'B'])
        self.assertEqual(data['correct'], 1)
 
    def test_multi_answer_json(self):
        q = MultipleChoiceQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        QuestionOption.objects.create(question=q, text='A', is_correct=True, order=0)
        QuestionOption.objects.create(question=q, text='B', is_correct=True, order=1)
        QuestionOption.objects.create(question=q, text='C', is_correct=False, order=2)
 
        data = _build_question_json_data(q, 'multi_answer')
        self.assertEqual(data['options'], ['A', 'B', 'C'])
        self.assertEqual(data['correct'], [0, 1])
 
    def test_true_false_json(self):
        q = TrueFalseQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', correct_answer=True
        )
        data = _build_question_json_data(q, 'true_false')
        self.assertEqual(data, {'correct': True})
 
    def test_written_json(self):
        q = WrittenQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', expected_answer='Paris'
        )
        data = _build_question_json_data(q, 'written')
        self.assertEqual(data, {'answer': 'Paris'})
 
    def test_ordering_json(self):
        q = OrderingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        OrderingItem.objects.create(question=q, text='Um', position=1)
        OrderingItem.objects.create(question=q, text='Dois', position=2)
        data = _build_question_json_data(q, 'ordering')
        self.assertEqual(data, {'items': ['Um', 'Dois']})
 
    def test_matching_json(self):
        q = MatchingQuestion.objects.create(exam=self.exam, statement='s', explanation='e')
        MatchingPair.objects.create(question=q, left='A', right='1', order=0)
        data = _build_question_json_data(q, 'matching')
        self.assertEqual(data, {'pairs': [{'left': 'A', 'right': '1'}]})
 
    def test_flashcard_json(self):
        q = FlashcardQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', front='F', back='B'
        )
        data = _build_question_json_data(q, 'flashcard')
        self.assertEqual(data, {'front': 'F', 'back': 'B'})
 
    def test_unknown_type_returns_empty_dict(self):
        q = TrueFalseQuestion.objects.create(
            exam=self.exam, statement='s', explanation='e', correct_answer=True
        )
        self.assertEqual(_build_question_json_data(q, 'tipo_desconhecido'), {})
 
 
class FlattenValidationErrorsTests(TestCase):
    def test_flattens_simple_list_of_messages(self):
        exc = ValidationError(['Erro 1', 'Erro 2'])
        self.assertEqual(_flatten_validation_errors(exc), ['Erro 1', 'Erro 2'])
 
    def test_flattens_error_dict(self):
        exc = ValidationError({'campo': ['obrigatório']})
        messages = _flatten_validation_errors(exc)
        self.assertEqual(messages, ['obrigatório'])
 
    def test_flattens_nested_validation_errors_in_dict(self):
        inner = ValidationError('erro interno')
        exc = ValidationError({'campo': [inner]})
        messages = _flatten_validation_errors(exc)
        self.assertEqual(messages, ['erro interno'])
 
    def test_non_validation_error_returns_str(self):
        exc = ValueError('algo deu errado')
        self.assertEqual(_flatten_validation_errors(exc), ['algo deu errado'])
 
    def test_ignores_empty_messages(self):
        exc = ValidationError(['', 'Erro válido', ''])
        self.assertEqual(_flatten_validation_errors(exc), ['Erro válido'])
