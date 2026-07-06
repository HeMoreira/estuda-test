from django.test import TestCase
from django.utils import timezone

from attempts.models import Attempt, AnswerRecord
from .factories import make_user, make_exam, add_multiple_choice, add_true_false


class AttemptModelTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.exam = make_exam(self.user)

    def test_str_representation(self):
        attempt = Attempt.objects.create(user=self.user, exam=self.exam)
        expected = f"{self.user.username} — {self.exam.name} ({attempt.started_at:%d/%m/%Y})"
        self.assertEqual(str(attempt), expected)

    def test_score_percent_none_when_score_not_set(self):
        attempt = Attempt.objects.create(user=self.user, exam=self.exam)
        self.assertIsNone(attempt.score)
        self.assertIsNone(attempt.score_percent())

    def test_score_percent_rounds_correctly(self):
        attempt = Attempt.objects.create(user=self.user, exam=self.exam, score=0.666)
        self.assertEqual(attempt.score_percent(), 67)

    def test_score_percent_zero(self):
        attempt = Attempt.objects.create(user=self.user, exam=self.exam, score=0.0)
        self.assertEqual(attempt.score_percent(), 0)

    def test_score_percent_full(self):
        attempt = Attempt.objects.create(user=self.user, exam=self.exam, score=1.0)
        self.assertEqual(attempt.score_percent(), 100)

    def test_default_ordering_is_most_recent_first(self):
        older = Attempt.objects.create(user=self.user, exam=self.exam)
        Attempt.objects.filter(pk=older.pk).update(
            started_at=timezone.now() - timezone.timedelta(days=1)
        )
        newer = Attempt.objects.create(user=self.user, exam=self.exam)
        attempts = list(Attempt.objects.all())
        self.assertEqual(attempts[0].pk, newer.pk)
        self.assertEqual(attempts[1].pk, older.pk)

    def test_finished_at_and_duration_default_to_none(self):
        attempt = Attempt.objects.create(user=self.user, exam=self.exam)
        self.assertIsNone(attempt.finished_at)
        self.assertIsNone(attempt.duration)


class AnswerRecordModelTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.exam = make_exam(self.user)
        self.attempt = Attempt.objects.create(user=self.user, exam=self.exam)
        self.question, self.correct_option = add_multiple_choice(self.exam)

    def test_create_answer_record(self):
        record = AnswerRecord.objects.create(
            attempt=self.attempt,
            question=self.question,
            given_answer=[str(self.correct_option.pk)],
            is_correct=True,
        )
        self.assertEqual(record.attempt, self.attempt)
        self.assertEqual(record.question.pk, self.question.pk)
        self.assertTrue(record.is_correct)
        self.assertEqual(record.given_answer, [str(self.correct_option.pk)])

    def test_given_answer_accepts_various_json_shapes(self):
        # dict (matching legacy format)
        record = AnswerRecord.objects.create(
            attempt=self.attempt,
            question=self.question,
            given_answer={'1': 'Paris'},
            is_correct=False,
        )
        record.refresh_from_db()
        self.assertEqual(record.given_answer, {'1': 'Paris'})

    def test_update_or_create_replaces_existing_answer(self):
        AnswerRecord.objects.update_or_create(
            attempt=self.attempt, question=self.question,
            defaults={'given_answer': ['1'], 'is_correct': False},
        )
        AnswerRecord.objects.update_or_create(
            attempt=self.attempt, question=self.question,
            defaults={'given_answer': ['2'], 'is_correct': True},
        )
        self.assertEqual(
            AnswerRecord.objects.filter(attempt=self.attempt, question=self.question).count(), 1
        )
        record = AnswerRecord.objects.get(attempt=self.attempt, question=self.question)
        self.assertEqual(record.given_answer, ['2'])
        self.assertTrue(record.is_correct)

    def test_true_false_answer_record_accepts_bool(self):
        tf_question = add_true_false(self.exam, order=2, correct_answer=True)
        record = AnswerRecord.objects.create(
            attempt=self.attempt, question=tf_question,
            given_answer=True, is_correct=True,
        )
        self.assertTrue(record.given_answer)