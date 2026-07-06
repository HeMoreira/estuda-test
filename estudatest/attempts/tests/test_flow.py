from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from attempts.models import Attempt, AnswerRecord
from .factories import (
    make_user, make_exam,
    add_multiple_choice, add_multi_answer, add_true_false, add_written,
    add_ordering, add_matching, add_flashcard,
)


class FullAttemptFlowAllCorrectTests(TestCase):
    """Percorre uma prova com um exemplar de cada tipo de questão,
    respondendo tudo corretamente, e confere o resultado final."""

    def setUp(self):
        self.user = make_user()
        self.exam = make_exam(self.user, name='Prova Completa')

        self.mc_question, self.mc_correct = add_multiple_choice(self.exam, order=1)
        self.ma_question, self.ma_correct = add_multi_answer(self.exam, order=2)
        self.tf_question = add_true_false(self.exam, order=3, correct_answer=True)
        self.wr_question = add_written(self.exam, order=4, expected_answer='python')
        self.or_question, self.or_items = add_ordering(self.exam, order=5)
        self.mt_question, self.mt_pairs = add_matching(self.exam, order=6)
        self.fc_question = add_flashcard(self.exam, order=7)

        self.client.force_login(self.user)

    def _post_answer(self, attempt_id, n, data):
        return self.client.post(
            reverse('attempts:question', args=[attempt_id, n]), data
        )

    def test_full_flow_all_correct_except_flashcard(self):
        start_response = self.client.post(reverse('attempts:start', args=[self.exam.pk]))
        attempt = Attempt.objects.get(user=self.user, exam=self.exam)
        self.assertRedirects(start_response, reverse('attempts:question', args=[attempt.id, 1]))

        # 1. Multiple choice - correct
        r = self._post_answer(attempt.id, 1, {'answer': [str(self.mc_correct.pk)]})
        self.assertTrue(r.context['feedback']['correct'])
        self.assertEqual(r.context['next_n'], 2)

        # 2. Multi answer - correct (all correct options selected)
        r = self._post_answer(attempt.id, 2, {'answer': [str(o.pk) for o in self.ma_correct]})
        self.assertTrue(r.context['feedback']['correct'])

        # 3. True/False - correct
        r = self._post_answer(attempt.id, 3, {'answer': 'true'})
        self.assertTrue(r.context['feedback']['correct'])

        # 4. Written - correct (case-insensitive, ignores accents/punctuation)
        r = self._post_answer(attempt.id, 4, {'answer': 'PYTHON!!'})
        self.assertTrue(r.context['feedback']['correct'])

        # 5. Ordering - correct order
        ordered_ids = [str(i.pk) for i in self.or_items]
        r = self._post_answer(attempt.id, 5, {'answer': ordered_ids})
        self.assertTrue(r.context['feedback']['correct'])

        # 6. Matching - correct pairing
        rights = [p.right for p in sorted(self.mt_pairs, key=lambda p: p.order)]
        r = self._post_answer(attempt.id, 6, {'answer': rights})
        self.assertTrue(r.context['feedback']['correct'])
        self.assertTrue(r.context['is_last'])
        self.assertIsNone(r.context['next_n'])

        # 7. Flashcard - self-graded, check_answer always False by design
        r = self._post_answer(attempt.id, 7, {'answer': 'true'})
        self.assertFalse(r.context['feedback']['correct'])
        self.assertTrue(r.context['is_last'])

        # All seven answers were recorded
        self.assertEqual(AnswerRecord.objects.filter(attempt=attempt).count(), 7)

        # Go to review: finalizes the attempt
        review_response = self.client.get(reverse('attempts:review', args=[attempt.id]))
        self.assertEqual(review_response.status_code, 200)

        attempt.refresh_from_db()
        self.assertIsNotNone(attempt.finished_at)
        self.assertIsNotNone(attempt.duration)
        # 6 correct out of 7 (flashcard always counted wrong)
        self.assertEqual(review_response.context['correct_count'], 6)
        self.assertEqual(review_response.context['total'], 7)
        self.assertAlmostEqual(attempt.score, 6 / 7)
        self.assertEqual(review_response.context['score_pct'], round(6 / 7 * 100))

        # Session progress cleared after finishing
        self.assertNotIn('attempt_progress', self.client.session)

        # Attempt is finished: question pages become inaccessible
        blocked = self.client.get(reverse('attempts:question', args=[attempt.id, 1]))
        self.assertEqual(blocked.status_code, 404)


class FullAttemptFlowAllWrongTests(TestCase):
    """Mesmo percurso, mas respondendo tudo errado -> score 0%."""

    def setUp(self):
        self.user = make_user()
        self.exam = make_exam(self.user, name='Prova Zero')
        self.mc_question, self.mc_correct = add_multiple_choice(self.exam, order=1)
        self.tf_question = add_true_false(self.exam, order=2, correct_answer=True)
        self.client.force_login(self.user)

    def test_full_flow_all_wrong(self):
        self.client.post(reverse('attempts:start', args=[self.exam.pk]))
        attempt = Attempt.objects.get(user=self.user, exam=self.exam)

        wrong_option = self.mc_question.options.exclude(pk=self.mc_correct.pk).first()
        self.client.post(reverse('attempts:question', args=[attempt.id, 1]),
                          {'answer': [str(wrong_option.pk)]})
        self.client.post(reverse('attempts:question', args=[attempt.id, 2]),
                          {'answer': 'false'})

        review = self.client.get(reverse('attempts:review', args=[attempt.id]))
        attempt.refresh_from_db()
        self.assertEqual(attempt.score, 0.0)
        self.assertEqual(review.context['score_pct'], 0)
        self.assertEqual(review.context['correct_count'], 0)


class RetakeExamFlowTests(TestCase):
    """Garante que refazer a prova cria uma nova tentativa independente."""

    def setUp(self):
        self.user = make_user()
        self.exam = make_exam(self.user, name='Prova Retake')
        self.question, self.correct_option = add_multiple_choice(self.exam)
        self.client.force_login(self.user)

    def test_retake_creates_second_independent_attempt(self):
        self.client.post(reverse('attempts:start', args=[self.exam.pk]))
        first_attempt = Attempt.objects.get(user=self.user, exam=self.exam)
        self.client.post(reverse('attempts:question', args=[first_attempt.id, 1]),
                          {'answer': [str(self.correct_option.pk)]})
        self.client.get(reverse('attempts:review', args=[first_attempt.id]))

        # Refazer prova (mesma ação do botão em review.html)
        self.client.post(reverse('attempts:start', args=[self.exam.pk]))

        self.assertEqual(Attempt.objects.filter(user=self.user, exam=self.exam).count(), 2)
        second_attempt = Attempt.objects.exclude(pk=first_attempt.pk).get(
            user=self.user, exam=self.exam
        )
        self.assertIsNone(second_attempt.finished_at)
        self.assertEqual(
            AnswerRecord.objects.filter(attempt=second_attempt).count(), 0
        )


class AttemptDurationTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.exam = make_exam(self.user)
        add_multiple_choice(self.exam)
        self.client.force_login(self.user)

    def test_duration_is_computed_from_started_at_to_review_time(self):
        self.client.post(reverse('attempts:start', args=[self.exam.pk]))
        attempt = Attempt.objects.get(user=self.user, exam=self.exam)

        # Simula que a tentativa começou há 5 minutos
        Attempt.objects.filter(pk=attempt.pk).update(
            started_at=timezone.now() - timedelta(minutes=5)
        )

        response = self.client.get(reverse('attempts:review', args=[attempt.id]))
        attempt.refresh_from_db()

        self.assertGreaterEqual(attempt.duration, timedelta(minutes=5))
        self.assertIn('min', response.context['duration_str'])