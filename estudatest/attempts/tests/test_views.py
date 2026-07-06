from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from attempts.models import Attempt, AnswerRecord
from .factories import (
    make_user, make_exam,
    add_multiple_choice, add_multi_answer, add_true_false, add_written,
    add_ordering, add_matching, add_flashcard,
)


class AttemptStartViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.exam = make_exam(self.user)

    def test_requires_login(self):
        url = reverse('attempts:start', args=[self.exam.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(response.url, [url])  # redirected away, to login

    def test_get_method_not_allowed(self):
        self.client.force_login(self.user)
        add_multiple_choice(self.exam)
        url = reverse('attempts:start', args=[self.exam.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_start_creates_attempt_and_redirects_to_first_question(self):
        self.client.force_login(self.user)
        add_multiple_choice(self.exam)
        url = reverse('attempts:start', args=[self.exam.pk])
        response = self.client.post(url)

        self.assertEqual(Attempt.objects.filter(user=self.user, exam=self.exam).count(), 1)
        attempt = Attempt.objects.get(user=self.user, exam=self.exam)
        self.assertRedirects(
            response,
            reverse('attempts:question', args=[attempt.id, 1]),
        )

    def test_start_initializes_session_progress(self):
        self.client.force_login(self.user)
        add_multiple_choice(self.exam)
        url = reverse('attempts:start', args=[self.exam.pk])
        self.client.post(url)

        session = self.client.session
        self.assertIn('attempt_progress', session)
        self.assertEqual(session['attempt_progress']['exam_id'], self.exam.id)
        self.assertEqual(session['attempt_progress']['answered'], [])

    def test_start_redirects_to_dashboard_when_exam_has_no_questions(self):
        self.client.force_login(self.user)
        url = reverse('attempts:start', args=[self.exam.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(Attempt.objects.count(), 0)

    def test_cannot_start_attempt_on_another_users_exam(self):
        other_user = make_user(username='intruso')
        self.client.force_login(other_user)
        add_multiple_choice(self.exam)
        url = reverse('attempts:start', args=[self.exam.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


class AttemptQuestionViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.exam = make_exam(self.user)

    def _start(self):
        self.client.force_login(self.user)
        self.client.post(reverse('attempts:start', args=[self.exam.pk]))
        return Attempt.objects.get(user=self.user, exam=self.exam)

    def test_requires_login(self):
        add_multiple_choice(self.exam)
        attempt = Attempt.objects.create(user=self.user, exam=self.exam)
        url = reverse('attempts:question', args=[attempt.id, 1])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_cannot_access_another_users_attempt(self):
        add_multiple_choice(self.exam)
        attempt = Attempt.objects.create(user=self.user, exam=self.exam)
        other_user = make_user(username='intruso2')
        self.client.force_login(other_user)
        url = reverse('attempts:question', args=[attempt.id, 1])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_get_renders_question_form(self):
        add_multiple_choice(self.exam)
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Paris')
        self.assertIsNone(response.context['feedback'])

    def test_n_below_range_redirects_to_review(self):
        add_multiple_choice(self.exam)
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 0])
        response = self.client.get(url)
        self.assertRedirects(response, reverse('attempts:review', args=[attempt.id]))

    def test_n_above_range_redirects_to_review(self):
        add_multiple_choice(self.exam)
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 99])
        response = self.client.get(url)
        self.assertRedirects(response, reverse('attempts:review', args=[attempt.id]))

    def test_post_multiple_choice_correct_answer(self):
        question, correct_option = add_multiple_choice(self.exam)
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        response = self.client.post(url, {'answer': [str(correct_option.pk)]})

        self.assertEqual(response.status_code, 200)
        record = AnswerRecord.objects.get(attempt=attempt, question=question)
        self.assertTrue(record.is_correct)
        self.assertTrue(response.context['feedback']['correct'])
        self.assertIsNone(response.context['next_n'])  # only 1 question -> last
        self.assertTrue(response.context['is_last'])

    def test_post_multiple_choice_wrong_answer(self):
        question, correct_option = add_multiple_choice(self.exam)
        wrong_option = question.options.exclude(pk=correct_option.pk).first()
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        response = self.client.post(url, {'answer': [str(wrong_option.pk)]})

        record = AnswerRecord.objects.get(attempt=attempt, question=question)
        self.assertFalse(record.is_correct)
        self.assertFalse(response.context['feedback']['correct'])
        self.assertEqual(response.context['feedback']['correct_answer'], 'Paris')

    def test_post_multi_answer_requires_exact_set(self):
        question, correct_opts = add_multi_answer(self.exam)
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        ids = [str(o.pk) for o in correct_opts]
        response = self.client.post(url, {'answer': ids})
        record = AnswerRecord.objects.get(attempt=attempt, question=question)
        self.assertTrue(record.is_correct)

    def test_post_true_false_correct(self):
        add_true_false(self.exam, correct_answer=True)
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        response = self.client.post(url, {'answer': 'true'})
        self.assertTrue(response.context['feedback']['correct'])

    def test_post_true_false_wrong(self):
        add_true_false(self.exam, correct_answer=True)
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        response = self.client.post(url, {'answer': 'false'})
        self.assertFalse(response.context['feedback']['correct'])

    def test_post_written_correct_ignores_accents_case_and_punctuation(self):
        add_written(self.exam, expected_answer='São Paulo')
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        response = self.client.post(url, {'answer': 'sao, paulo!!'})
        self.assertTrue(response.context['feedback']['correct'])

    def test_post_written_accepts_alternative(self):
        add_written(self.exam, expected_answer='python',
                     accepted_alternatives=['py'])
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        response = self.client.post(url, {'answer': 'PY'})
        self.assertTrue(response.context['feedback']['correct'])

    def test_post_ordering_correct(self):
        question, items = add_ordering(self.exam)
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        ordered_ids = [str(i.pk) for i in items]  # already in correct order
        response = self.client.post(url, {'answer': ordered_ids})
        self.assertTrue(response.context['feedback']['correct'])

    def test_post_ordering_wrong_order(self):
        question, items = add_ordering(self.exam)
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        reversed_ids = [str(i.pk) for i in reversed(items)]
        response = self.client.post(url, {'answer': reversed_ids})
        self.assertFalse(response.context['feedback']['correct'])

    def test_ordering_shuffle_is_stored_in_session_and_stable(self):
        add_ordering(self.exam)
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        response1 = self.client.get(url)
        shuffle_key = f'shuffle_{attempt.id}_{response1.context["question"].id}'
        self.assertIn(shuffle_key, self.client.session)
        first_shuffle = self.client.session[shuffle_key]

        response2 = self.client.get(url)
        second_shuffle = self.client.session[shuffle_key]
        self.assertEqual(first_shuffle, second_shuffle)

    def test_post_matching_correct(self):
        question, pairs = add_matching(self.exam)
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        rights_in_order = [p.right for p in sorted(pairs, key=lambda p: p.order)]
        response = self.client.post(url, {'answer': rights_in_order})
        self.assertTrue(response.context['feedback']['correct'])

    def test_post_matching_wrong(self):
        question, pairs = add_matching(self.exam)
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        rights_reversed = [p.right for p in sorted(pairs, key=lambda p: -p.order)]
        response = self.client.post(url, {'answer': rights_reversed})
        self.assertFalse(response.context['feedback']['correct'])

    def test_post_flashcard_is_never_marked_correct(self):
        add_flashcard(self.exam)
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        response = self.client.post(url, {'answer': 'true'})
        self.assertFalse(response.context['feedback']['correct'])

    def test_answering_same_question_twice_does_not_duplicate_answered_list(self):
        question, correct_option = add_multiple_choice(self.exam)
        attempt = self._start()
        url = reverse('attempts:question', args=[attempt.id, 1])
        self.client.post(url, {'answer': [str(correct_option.pk)]})
        self.client.post(url, {'answer': [str(correct_option.pk)]})

        session = self.client.session
        self.assertEqual(session['attempt_progress']['answered'].count(question.id), 1)
        self.assertEqual(
            AnswerRecord.objects.filter(attempt=attempt, question=question).count(), 1
        )

    def test_finished_attempt_returns_404_on_question_page(self):
        add_multiple_choice(self.exam)
        attempt = self._start()
        # simulate finishing the attempt
        self.client.get(reverse('attempts:review', args=[attempt.id]))
        url = reverse('attempts:question', args=[attempt.id, 1])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class AttemptReviewViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.exam = make_exam(self.user)

    def _start(self):
        self.client.force_login(self.user)
        self.client.post(reverse('attempts:start', args=[self.exam.pk]))
        return Attempt.objects.get(user=self.user, exam=self.exam)

    def test_requires_login(self):
        add_multiple_choice(self.exam)
        attempt = Attempt.objects.create(user=self.user, exam=self.exam)
        url = reverse('attempts:review', args=[attempt.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_cannot_review_another_users_attempt(self):
        add_multiple_choice(self.exam)
        attempt = Attempt.objects.create(user=self.user, exam=self.exam)
        other_user = make_user(username='intruso3')
        self.client.force_login(other_user)
        url = reverse('attempts:review', args=[attempt.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_review_finalizes_attempt_once(self):
        add_multiple_choice(self.exam)
        attempt = self._start()
        url = reverse('attempts:review', args=[attempt.id])

        self.client.get(url)
        attempt.refresh_from_db()
        self.assertIsNotNone(attempt.finished_at)
        self.assertIsNotNone(attempt.duration)
        first_finished_at = attempt.finished_at

        # visiting again should not change finished_at
        self.client.get(url)
        attempt.refresh_from_db()
        self.assertEqual(attempt.finished_at, first_finished_at)

    def test_review_clears_session_progress(self):
        add_multiple_choice(self.exam)
        attempt = self._start()
        self.assertIn('attempt_progress', self.client.session)
        self.client.get(reverse('attempts:review', args=[attempt.id]))
        self.assertNotIn('attempt_progress', self.client.session)

    def test_review_computes_score_percent_and_counts(self):
        q1, opt1 = add_multiple_choice(self.exam, order=1)
        q2 = add_true_false(self.exam, order=2, correct_answer=True)
        attempt = self._start()

        self.client.post(reverse('attempts:question', args=[attempt.id, 1]),
                          {'answer': [str(opt1.pk)]})
        self.client.post(reverse('attempts:question', args=[attempt.id, 2]),
                          {'answer': 'false'})  # wrong

        response = self.client.get(reverse('attempts:review', args=[attempt.id]))
        self.assertEqual(response.context['score_pct'], 50)
        self.assertEqual(response.context['correct_count'], 1)
        self.assertEqual(response.context['total'], 2)

    def test_review_with_no_answers_scores_zero(self):
        add_multiple_choice(self.exam)
        attempt = self._start()
        response = self.client.get(reverse('attempts:review', args=[attempt.id]))
        self.assertEqual(response.context['score_pct'], 0)

    def test_review_given_display_for_multiple_choice(self):
        question, correct_option = add_multiple_choice(self.exam)
        attempt = self._start()
        self.client.post(reverse('attempts:question', args=[attempt.id, 1]),
                          {'answer': [str(correct_option.pk)]})
        response = self.client.get(reverse('attempts:review', args=[attempt.id]))
        answer_data = response.context['answer_data']
        self.assertEqual(answer_data[0]['given_display'], 'Paris')
        self.assertEqual(answer_data[0]['correct_display'], 'Paris')

    def test_review_given_display_for_ordering(self):
        question, items = add_ordering(self.exam)
        attempt = self._start()
        ids = [str(i.pk) for i in items]
        self.client.post(reverse('attempts:question', args=[attempt.id, 1]), {'answer': ids})
        response = self.client.get(reverse('attempts:review', args=[attempt.id]))
        answer_data = response.context['answer_data']
        self.assertEqual(answer_data[0]['given_display'], 'Um → Dois → Três')

    def test_review_given_display_for_matching(self):
        question, pairs = add_matching(self.exam)
        attempt = self._start()
        rights = [p.right for p in sorted(pairs, key=lambda p: p.order)]
        self.client.post(reverse('attempts:question', args=[attempt.id, 1]), {'answer': rights})
        response = self.client.get(reverse('attempts:review', args=[attempt.id]))
        answer_data = response.context['answer_data']
        self.assertIn('Brasil → Brasília', answer_data[0]['given_display'])
        self.assertIn('França → Paris', answer_data[0]['given_display'])