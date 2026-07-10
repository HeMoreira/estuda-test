import json
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError

from .services import QuestionService
from attempts.models import Attempt
from .utils import (
    save_exam_with_default_category_if_needed,
    flatten_validation_errors,
    build_question_edit_data,
    build_question_preview_data,
)
from .models import Exam, Question
from .forms import ExamForm, QuestionTypeForm
from .question_types import is_registered_type
from .spaced_repetition import get_urgency_ratio, urgency_color

logger = logging.getLogger(__name__)


@login_required
def exam_create(request):
    if request.method == 'POST':
        form = ExamForm(request.user, request.POST)
        if form.is_valid():
            exam = save_exam_with_default_category_if_needed(request, form)
            return redirect('exams:edit', pk=exam.pk)
    else:
        form = ExamForm(request.user)
    return render(request, 'exams/exam_form.html', {'form': form, 'action': 'create'})


@login_required
def exam_edit(request, pk):
    exam = get_object_or_404(Exam, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ExamForm(request.user, request.POST, instance=exam)
        if form.is_valid():
            exam = save_exam_with_default_category_if_needed(request, form)
            return redirect('exams:edit', pk=exam.pk)
    else:
        form = ExamForm(request.user, instance=exam)

    questions = exam.questions.order_by('order').prefetch_related('options')
    return render(request, 'exams/exam_form.html', {
        'form': form, 'exam': exam, 'questions': questions, 'action': 'edit',
    })


def _format_duration(duration):
    if not duration:
        return None
    minutes, seconds = divmod(int(duration.total_seconds()), 60)
    return f'{minutes}min {seconds:02d}s'


@login_required
def exam_detail_json(request, pk):
    exam = get_object_or_404(Exam, pk=pk, user=request.user)
    attempts = Attempt.objects.filter(exam=exam, user=request.user, finished_at__isnull=False)
    attempt_count = attempts.count()
    last_attempt = attempts.order_by('-started_at').first()
    avg_duration = attempts.filter(duration__isnull=False).aggregate(avg=Avg('duration'))['avg']

    ratio = get_urgency_ratio(attempt_count, last_attempt.started_at if last_attempt else None)

    return JsonResponse({
        'id': exam.id,
        'name': exam.name,
        'category': exam.category.name if exam.category else None,
        'question_count': exam.question_count(),
        'updated_at': exam.updated_at.strftime('%d/%m/%Y'),
        'attempt_count': attempt_count,
        'last_attempt_date': last_attempt.started_at.strftime('%d/%m/%Y') if last_attempt else None,
        'last_duration': _format_duration(last_attempt.duration) if last_attempt else None,
        'avg_duration': _format_duration(avg_duration),
        'score_percent': last_attempt.score_percent() if last_attempt else None,
        'urgency_color': urgency_color(ratio),
        'urgency_ratio': ratio,
    })


@login_required
@require_http_methods(['DELETE'])
def exam_delete(request, pk):
    exam = get_object_or_404(Exam, pk=pk, user=request.user)
    exam.delete()
    return JsonResponse({'ok': True})


# ── Fluxo de questões ──

def _render_type_selector(request, exam, redirect_path):
    type_form = QuestionTypeForm(request.POST or None)
    if request.method == 'POST' and type_form.is_valid():
        chosen = type_form.cleaned_data['question_type']
        return redirect(f'{redirect_path}?question_type={chosen}')
    return render(request, 'exams/question_form.html', {'type_form': type_form, 'exam': exam})


@login_required
def question_add(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk, user=request.user)
    question_type = request.POST.get('question_type') or request.GET.get('question_type')

    if not is_registered_type(question_type):
        return _render_type_selector(request, exam, request.path)

    errors = []
    preview_data = {}
    if request.method == 'POST':
        try:
            QuestionService.create_question(exam, question_type, request.POST)
            return redirect('exams:edit', pk=exam.pk)
        except ValidationError as exc:
            errors = flatten_validation_errors(exc)
        except Exception:
            logger.exception('Erro ao criar questão tipo=%s exam=%s', question_type, exam.pk)
            errors = ['Ocorreu um erro inesperado ao salvar a questão. Tente novamente.']
        preview_data = build_question_preview_data(question_type, request.POST)

    return render(request, 'exams/question_form.html', {
        'type_form': QuestionTypeForm(initial={'question_type': question_type}),
        'exam': exam, 'question_type': question_type, 'errors': errors, 'action': 'add',
        'statement': request.POST.get('statement', ''),
        'explanation': request.POST.get('explanation', ''),
        'question_data_json': json.dumps(preview_data) if preview_data else None,
    })



@login_required
def question_edit(request, exam_pk, pk):
    exam = get_object_or_404(Exam, pk=exam_pk, user=request.user)
    instance = get_object_or_404(Question, pk=pk, exam=exam)
    question_type = instance.question_type

    errors = []
    if request.method == 'POST':
        try:
            QuestionService.update_question(instance, question_type, request.POST)
            return redirect('exams:edit', pk=exam.pk)
        except ValidationError as exc:
            errors = flatten_validation_errors(exc)
        except Exception:
            logger.exception('Erro ao atualizar questão pk=%s', instance.pk)
            errors = ['Ocorreu um erro inesperado ao atualizar a questão.']
        preview_data = build_question_preview_data(question_type, request.POST)
        statement = request.POST.get('statement', instance.statement)
        explanation = request.POST.get('explanation', instance.explanation)
    else:
        preview_data = build_question_edit_data(instance, question_type)
        statement = instance.statement
        explanation = instance.explanation

    return render(request, 'exams/question_form.html', {
        'type_form': QuestionTypeForm(initial={'question_type': question_type}),
        'exam': exam, 'question': instance, 'question_type': question_type,
        'question_data_json': json.dumps(preview_data),
        'errors': errors, 'action': 'edit',
        'statement': statement,
        'explanation': explanation,
    })


@login_required
@require_http_methods(['DELETE'])
def question_delete(request, exam_pk, pk):
    exam = get_object_or_404(Exam, pk=exam_pk, user=request.user)
    question = get_object_or_404(Question, pk=pk, exam=exam)
    question.delete()
    for index, remaining in enumerate(exam.questions.order_by('order')):
        if remaining.order != index:
            remaining.order = index
            remaining.save(update_fields=['order'])
    return JsonResponse({'ok': True})