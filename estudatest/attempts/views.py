# attempts/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.decorators.http import require_POST
from exams.models import Exam, Question
from .models import Attempt, AnswerRecord
import random

SESSION_KEY = 'attempt_progress'


@login_required
@require_POST
def attempt_start(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk, user=request.user)
    if exam.question_count() == 0:
        return redirect('dashboard')

    attempt = Attempt.objects.create(user=request.user, exam=exam)
    request.session[SESSION_KEY] = {
        'attempt_id': attempt.id,
        'exam_id': exam.id,
        'answered': [],
    }
    return redirect('attempts:question', attempt_id=attempt.id, n=1)


@login_required
def attempt_question(request, attempt_id, n):
    attempt = get_object_or_404(Attempt, pk=attempt_id, user=request.user, finished_at__isnull=True)
    exam = attempt.exam
    
    # O django-polymorphic traz as instâncias corretas e os dados necessários eficientemente
    # prefetch apenas opções por padrão; itens/pares serão carregados quando necessário
    questions = list(exam.questions.order_by('order').prefetch_related('options'))
    total = len(questions)

    if n < 1 or n > total:
        return redirect('attempts:review', attempt_id=attempt.id)

    question = questions[n - 1]
    progress_pct = round((n - 1) / total * 100)

    session = request.session.get(SESSION_KEY, {})
    answered_ids = session.get('answered', [])

    shuffle_key = f'shuffle_{attempt_id}_{question.id}'
    shuffled = request.session.get(shuffle_key)

    # Lógica de embaralhamento adaptada para ler as propriedades das novas classes
    if shuffled is None:
        if question.question_type == 'ordering':
            # 'items' agora é um relacionamento do modelo OrderingQuestion
            items = list(question.items.all())
            indexed = [(item.id, item.text) for item in items]
            random.shuffle(indexed)
            shuffled = {'indexed': indexed}
        elif question.question_type == 'matching':
            # 'pairs' agora é um relacionamento do modelo MatchingQuestion
            rights = [p.right for p in question.pairs.all()]
            random.shuffle(rights)
            shuffled = {'rights': rights}
        else:
            shuffled = {}
        request.session[shuffle_key] = shuffled
        request.session.modified = True

    if request.method == 'POST':
        if question.question_type in ['multi_answer', 'ordering', 'matching', 'multiple_choice']:
            given = request.POST.getlist('answer')
        else:
            given = request.POST.get('answer', '')

        # Método direto, limpo e polimórfico gerado pela nova estrutura
        correct = question.check_answer(given)
        
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
            'correct_answer': question.correct_answer_display(),  # Centralizado no Model
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
            'shuffled': shuffled,
        })

    return render(request, 'attempts/question.html', {
        'attempt': attempt,
        'question': question,
        'n': n,
        'total': total,
        'progress_pct': progress_pct,
        'feedback': None,
        'shuffled': shuffled,
    })


@login_required
def attempt_review(request, attempt_id):
    attempt = get_object_or_404(Attempt, pk=attempt_id, user=request.user)

    if attempt.finished_at is None:
        attempt.finished_at = timezone.now()
        attempt.duration = attempt.finished_at - attempt.started_at

        answers = AnswerRecord.objects.filter(attempt=attempt)
        total_q = attempt.exam.question_count()
        correct_count = answers.filter(is_correct=True).count()
        attempt.score = correct_count / total_q if total_q > 0 else 0.0
        attempt.save()

        if SESSION_KEY in request.session:
            del request.session[SESSION_KEY]

    # select_related beneficia-se do polymorphic carregando os tipos reais de uma vez só
    answers = AnswerRecord.objects.filter(attempt=attempt).select_related('question')
    answer_data = []
    for ar in answers:
        q = ar.question
        given = ar.given_answer

        # Build a human-readable representation of the given answer
        given_display = '—'
        try:
            if q.question_type in ('multiple_choice', 'multi_answer'):
                if given is None:
                    given_display = '—'
                else:
                    if isinstance(given, (list, tuple)):
                        ids = [str(x) for x in given]
                    else:
                        ids = [str(given)]
                    opts = q.options.filter(pk__in=ids).order_by('order')
                    given_display = ', '.join(o.text for o in opts if o.text)
            elif q.question_type == 'true_false':
                if isinstance(given, bool):
                    given_display = 'Verdadeiro' if given else 'Falso'
                else:
                    given_display = 'Verdadeiro' if str(given).lower() in ('true', '1', 'verdadeiro') else 'Falso'
            elif q.question_type == 'written':
                given_display = given or '—'
            elif q.question_type == 'ordering':
                if isinstance(given, (list, tuple)):
                    ids = [int(x) for x in given]
                    items = {it.pk: it for it in q.items.all()}
                    given_display = ' → '.join(items[i].text for i in ids if i in items)
                else:
                    given_display = str(given)
            elif q.question_type == 'matching':
                if isinstance(given, dict):
                    pairs = {str(p.pk): p for p in q.pairs.all()}
                    parts = []
                    for pid, right in given.items():
                        p = pairs.get(str(pid))
                        if p:
                            parts.append(f"{p.left} → {right}")
                    given_display = '; '.join(parts)
                elif isinstance(given, (list, tuple)):
                    pairs = list(q.pairs.order_by('order'))
                    parts = []
                    for left, right in zip(pairs, given):
                        parts.append(f"{left.left} → {right}")
                    given_display = '; '.join(parts)
                else:
                    given_display = str(given)
            elif q.question_type == 'flashcard':
                given_display = 'Acertei' if str(given).lower() in ('true', '1', 'verdadeiro') else 'Errei'
            else:
                given_display = str(given) if given is not None else '—'
        except Exception:
            given_display = str(given)

        try:
            correct_disp = q.correct_answer_display()
        except Exception:
            correct_disp = '—'

        answer_data.append({
            'record': ar,
            'question': q,
            'correct_display': correct_disp,
            'given_display': given_display,
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