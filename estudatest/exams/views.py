from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError

from .services import QuestionService
  
from attempts.models import Attempt
from .utils import save_exam_with_default_category_if_needed, _flatten_validation_errors, _build_question_json_data
from .models import Exam, Question
from .forms import ExamForm, QuestionTypeForm, QUESTION_TYPE_REGISTRY
from .spaced_repetition import get_urgency_ratio, urgency_color
import json


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
    
    # prefetch apenas opções por padrão; itens/pares serão carregados sob demanda
    questions = exam.questions.order_by('order').prefetch_related('options')
    
    return render(request, 'exams/exam_form.html', {
        'form': form,
        'exam': exam,
        'questions': questions,
        'action': 'edit',
    })
  
  
@login_required
def exam_detail_json(request, pk):
    exam = get_object_or_404(Exam, pk=pk, user=request.user)
    attempts = Attempt.objects.filter(exam=exam, user=request.user, finished_at__isnull=False)
    attempt_count = attempts.count()
    last_attempt = attempts.order_by('-started_at').first()
    avg_duration = attempts.filter(duration__isnull=False).aggregate(avg=Avg('duration'))['avg']
  
    def fmt_duration(d):
        if not d:
            return None
        total = int(d.total_seconds())
        m, s = divmod(total, 60)
        return f'{m}min {s:02d}s'
  
    ratio = get_urgency_ratio(attempt_count, last_attempt.started_at if last_attempt else None)
    color = urgency_color(ratio)
  
    return JsonResponse({
        'id': exam.id,
        'name': exam.name,
        'category': exam.category.name if exam.category else None,
        'question_count': exam.question_count(),
        'updated_at': exam.updated_at.strftime('%d/%m/%Y'),
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
def exam_delete(request, pk):
    exam = get_object_or_404(Exam, pk=pk, user=request.user)
    exam.delete()
    return JsonResponse({'ok': True})


@login_required
def question_add(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk, user=request.user)
    question_type = request.POST.get('question_type') or request.GET.get('question_type')

    if question_type not in QUESTION_TYPE_REGISTRY:
        type_form = QuestionTypeForm(request.POST or None)
        if request.method == 'POST' and type_form.is_valid():
            return redirect(f"{request.path}?question_type={type_form.cleaned_data['question_type']}")
        return render(request, 'exams/question_form.html', {
            'type_form': type_form, 'exam': exam,
        })

    FormClass, FormSetClass = QUESTION_TYPE_REGISTRY[question_type]
    form = FormClass(request.POST or None)
    formset = FormSetClass(request.POST or None, instance=form.instance) if FormSetClass else None
    errors = []

    if request.method == 'POST':
        if any(k in request.POST for k in ('data_options', 'data_items', 'data_pairs_left', 'data_front')):
            try:
                with transaction.atomic():
                    QuestionService.create_question(exam, question_type, request.POST)
                return redirect('exams:edit', pk=exam.pk)
            except ValidationError as exc:
                errors = _flatten_validation_errors(exc)
            except Exception:
                errors = ['Ocorreu um erro ao salvar a estrutura dinâmica da questão.']
    
    type_form = QuestionTypeForm(request.POST or None, initial={'question_type': question_type})
    return render(request, 'exams/question_form.html', {
        'form': form, 
        'type_form': type_form,
        'formset': formset, 
        'exam': exam,
        'question_type': question_type, 
        'errors': errors, 
        'action': 'add',
    })


@login_required
def question_edit(request, exam_pk, pk):
    exam = get_object_or_404(Exam, pk=exam_pk, user=request.user)
    instance = get_object_or_404(Question, pk=pk, exam=exam)
    question_type = instance.question_type

    if question_type not in QUESTION_TYPE_REGISTRY:
        type_form = QuestionTypeForm(request.POST or None)
        if request.method == 'POST' and type_form.is_valid():
            return redirect(f"{request.path}?question_type={type_form.cleaned_data['question_type']}")
        return render(request, 'exams/question_form.html', {
            'type_form': type_form, 'exam': exam,
        })
  
    FormClass, FormSetClass = QUESTION_TYPE_REGISTRY[question_type]
    form = FormClass(request.POST or None, instance=instance)
    formset = FormSetClass(request.POST or None, instance=instance) if FormSetClass else None
    errors = []
  
    if request.method == 'POST':
        if any(k.startswith('data_') for k in request.POST.keys()):
            try:
                with transaction.atomic():
                    QuestionService.update_question(instance, question_type, request.POST)
                return redirect('exams:edit', pk=exam.pk)
            except ValidationError as e:
                errors = e.messages
            except Exception:
                errors = ['Ocorreu um erro ao atualizar os dados dinâmicos da questão.']
  
    # Construir dados simples para popular o editor via JS
    qdata = _build_question_json_data(instance, question_type)

    type_form = QuestionTypeForm(request.POST or None, initial={'question_type': question_type})
    context = {
        'form': form, 'formset': formset, 'exam': exam, 'question': instance,
        'question_data_json': json.dumps(qdata), 'question_type': question_type,
        'errors': errors, 'action': 'edit',
        'type_form': type_form,
    }
    return render(request, 'exams/question_form.html', context)


@login_required
@require_http_methods(['DELETE'])
def question_delete(request, exam_pk, pk):
    exam = get_object_or_404(Exam, pk=exam_pk, user=request.user)
    question = get_object_or_404(Question, pk=pk, exam=exam)
    question.delete()
    for i, q in enumerate(exam.questions.order_by('order')):
        if q.order != i:
            q.order = i
            q.save(update_fields=['order'])
    return JsonResponse({'ok': True})