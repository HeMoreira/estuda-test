from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.decorators.http import require_POST
from tests_app.models import Test, Question
from tests_app.question_validator import check_answer
from .models import Attempt, AnswerRecord


SESSION_KEY = 'attempt_progress'


@login_required
@require_POST
def attempt_start(request, test_pk):
    test = get_object_or_404(Test, pk=test_pk, user=request.user)
    if test.question_count() == 0:
        return redirect('dashboard')

    attempt = Attempt.objects.create(user=request.user, test=test)
    request.session[SESSION_KEY] = {
        'attempt_id': attempt.id,
        'test_id': test.id,
        'answered': [],
    }
    return redirect('attempts:question', attempt_id=attempt.id, n=1)


@login_required
def attempt_question(request, attempt_id, n):
    attempt = get_object_or_404(Attempt, pk=attempt_id, user=request.user, finished_at__isnull=True)
    test = attempt.test
    questions = list(test.questions.order_by('order'))
    total = len(questions)

    if n < 1 or n > total:
        return redirect('attempts:review', attempt_id=attempt.id)

    question = questions[n - 1]
    progress_pct = round((n - 1) / total * 100)

    session = request.session.get(SESSION_KEY, {})
    answered_ids = session.get('answered', [])

    if request.method == 'POST':
        if question.question_type in ['multi_answer', 'ordering', 'matching']:
            given = request.POST.getlist('answer')
        else:
            given = request.POST.get('answer', '')

        correct = check_answer(question, given)
        AnswerRecord.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={'given_answer': given, 'is_correct': correct},
        )

        if question.id not in answered_ids:
            answered_ids.append(question.id)
            session['answered'] = answered_ids
            request.session[SESSION_KEY] = session
            request.session.modified = True

        feedback = {
            'correct': correct,
            'explanation': question.explanation,
            'correct_answer': _get_correct_display(question),
        }

        return render(request, 'attempts/question.html', {
            'attempt': attempt,
            'question': question,
            'n': n,
            'total': total,
            'progress_pct': progress_pct,
            'feedback': feedback,
            'next_n': n + 1 if n < total else None,
            'is_last': n == total,
        })

    return render(request, 'attempts/question.html', {
        'attempt': attempt,
        'question': question,
        'n': n,
        'total': total,
        'progress_pct': progress_pct,
        'feedback': None,
    })


def _get_correct_display(question):
    qt = question.question_type
    data = question.data
    if qt == 'multiple_choice':
        opts = data.get('options', [])
        idx = data.get('correct', 0)
        return opts[idx] if idx < len(opts) else ''
    elif qt == 'multi_answer':
        opts = data.get('options', [])
        return ', '.join(opts[i] for i in data.get('correct', []) if i < len(opts))
    elif qt == 'true_false':
        return 'Verdadeiro' if data.get('correct') else 'Falso'
    elif qt == 'written':
        return data.get('answer', '')
    elif qt == 'ordering':
        return ' → '.join(data.get('items', []))
    elif qt == 'matching':
        return '; '.join(f"{p['left']} = {p['right']}" for p in data.get('pairs', []))
    elif qt == 'flashcard':
        return data.get('back', '')
    return ''


@login_required
def attempt_review(request, attempt_id):
    attempt = get_object_or_404(Attempt, pk=attempt_id, user=request.user)

    if attempt.finished_at is None:
        attempt.finished_at = timezone.now()
        attempt.duration = attempt.finished_at - attempt.started_at

        answers = AnswerRecord.objects.filter(attempt=attempt)
        total_q = attempt.test.question_count()
        correct_count = answers.filter(is_correct=True).count()
        attempt.score = correct_count / total_q if total_q > 0 else 0.0
        attempt.save()

        if SESSION_KEY in request.session:
            del request.session[SESSION_KEY]

    answers = AnswerRecord.objects.filter(attempt=attempt).select_related('question')
    answer_data = []
    for ar in answers:
        answer_data.append({
            'record': ar,
            'question': ar.question,
            'correct_display': _get_correct_display(ar.question),
        })

    total_secs = int(attempt.duration.total_seconds()) if attempt.duration else 0
    m, s = divmod(total_secs, 60)
    duration_str = f'{m}min {s:02d}s'

    return render(request, 'attempts/review.html', {
        'attempt': attempt,
        'answer_data': answer_data,
        'duration_str': duration_str,
        'score_pct': attempt.score_percent(),
        'correct_count': sum(1 for a in answer_data if a['record'].is_correct),
        'total': len(answer_data),
    })
