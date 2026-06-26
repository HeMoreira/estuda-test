import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Avg
from attempts.models import Attempt
from .models import Test, Question
from .forms import TestForm, QuestionForm
from .question_validator import validate_question_data
from .spaced_repetition import get_urgency_ratio, urgency_color


@login_required
def test_create(request):
    if request.method == 'POST':
        form = TestForm(request.user, request.POST)
        if form.is_valid():
            test = form.save(commit=False)
            test.user = request.user
            test.save()
            return redirect('tests_app:edit', pk=test.pk)
    else:
        form = TestForm(request.user)
    return render(request, 'tests_app/test_form.html', {'form': form, 'action': 'create'})


@login_required
def test_edit(request, pk):
    test = get_object_or_404(Test, pk=pk, user=request.user)
    if request.method == 'POST':
        form = TestForm(request.user, request.POST, instance=test)
        if form.is_valid():
            form.save()
            return redirect('tests_app:edit', pk=test.pk)
    else:
        form = TestForm(request.user, instance=test)
    questions = test.questions.order_by('order')
    return render(request, 'tests_app/test_form.html', {
        'form': form,
        'test': test,
        'questions': questions,
        'action': 'edit',
    })


@login_required
def test_detail_json(request, pk):
    test = get_object_or_404(Test, pk=pk, user=request.user)
    attempts = Attempt.objects.filter(test=test, user=request.user, finished_at__isnull=False)
    attempt_count = attempts.count()
    last_attempt  = attempts.order_by('-started_at').first()
    avg_duration  = attempts.filter(duration__isnull=False).aggregate(avg=Avg('duration'))['avg']

    def fmt_duration(d):
        if not d:
            return None
        total = int(d.total_seconds())
        m, s = divmod(total, 60)
        return f'{m}min {s:02d}s'

    ratio = get_urgency_ratio(attempt_count, last_attempt.started_at if last_attempt else None)
    color = urgency_color(ratio)

    return JsonResponse({
        'id': test.id,
        'name': test.name,
        'category': test.category.name if test.category else None,
        'question_count': test.question_count(),
        'updated_at': test.updated_at.strftime('%d/%m/%Y'),
        'attempt_count': attempt_count,
        'last_attempt_date': last_attempt.started_at.strftime('%d/%m/%Y') if last_attempt else None,
        'last_duration': fmt_duration(last_attempt.duration) if last_attempt else None,
        'avg_duration': fmt_duration(avg_duration),
        'score_percent': last_attempt.score_percent() if last_attempt else None,
        'urgency_color': color,
        'urgency_ratio': ratio,
    })


@login_required
@require_http_methods(['DELETE'])
def test_delete(request, pk):
    test = get_object_or_404(Test, pk=pk, user=request.user)
    test.delete()
    return JsonResponse({'ok': True})


def _extract_question_data(post, question_type):
    """Extract structured data from POST depending on question type."""
    if question_type == 'multiple_choice':
        return {
            'options':  post.getlist('data_options'),
            'correct':  post.get('data_correct', '0'),
        }
    elif question_type == 'multi_answer':
        return {
            'options': post.getlist('data_options'),
            'correct': post.getlist('data_correct'),
        }
    elif question_type == 'true_false':
        return {'correct': post.get('data_correct', 'false')}
    elif question_type == 'written':
        return {'answer': post.get('data_answer', '')}
    elif question_type == 'ordering':
        return {'items': post.getlist('data_items')}
    elif question_type == 'matching':
        return {
            'pairs_left':  post.getlist('data_pairs_left'),
            'pairs_right': post.getlist('data_pairs_right'),
        }
    elif question_type == 'flashcard':
        return {
            'front': post.get('data_front', ''),
            'back':  post.get('data_back',  ''),
        }
    return {}


@login_required
def question_add(request, test_pk):
    test = get_object_or_404(Test, pk=test_pk, user=request.user)
    errors = []
    form   = QuestionForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            qt       = form.cleaned_data['question_type']
            raw_data = _extract_question_data(request.POST, qt)
            cleaned_data, errors = validate_question_data(qt, raw_data)
            if not errors:
                q       = form.save(commit=False)
                q.test  = test
                q.data  = cleaned_data
                q.order = test.questions.count()
                q.save()
                return redirect('tests_app:edit', pk=test.pk)

    return render(request, 'tests_app/question_form.html', {
        'form': form, 'test': test, 'errors': errors, 'action': 'add',
    })


@login_required
def question_edit(request, test_pk, pk):
    test     = get_object_or_404(Test, pk=test_pk, user=request.user)
    question = get_object_or_404(Question, pk=pk, test=test)
    errors   = []
    form     = QuestionForm(request.POST or None, instance=question)

    if request.method == 'POST':
        if form.is_valid():
            qt       = form.cleaned_data['question_type']
            raw_data = _extract_question_data(request.POST, qt)
            cleaned_data, errors = validate_question_data(qt, raw_data)
            if not errors:
                q      = form.save(commit=False)
                q.data = cleaned_data
                q.save()
                return redirect('tests_app:edit', pk=test.pk)

    return render(request, 'tests_app/question_form.html', {
        'form': form,
        'test': test,
        'question': question,
        'question_data_json': json.dumps(question.data),
        'errors': errors,
        'action': 'edit',
    })


@login_required
@require_http_methods(['DELETE'])
def question_delete(request, test_pk, pk):
    test     = get_object_or_404(Test, pk=test_pk, user=request.user)
    question = get_object_or_404(Question, pk=pk, test=test)
    question.delete()
    for i, q in enumerate(test.questions.order_by('order')):
        if q.order != i:
            q.order = i
            q.save(update_fields=['order'])
    return JsonResponse({'ok': True})
