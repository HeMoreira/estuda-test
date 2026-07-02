from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
  
from attempts.models import Attempt
from .utils import get_or_create_default_category
from .models import (
    Exam, Question,
    MultipleChoiceQuestion, MultiAnswerQuestion, TrueFalseQuestion,
    WrittenQuestion, OrderingQuestion, MatchingQuestion, FlashcardQuestion,
    QuestionOption, OrderingItem, MatchingPair,
)
from .forms import ExamForm, QuestionTypeForm, QUESTION_TYPE_REGISTRY
from .spaced_repetition import get_urgency_ratio, urgency_color
import json


@login_required
def exam_create(request):
    if request.method == 'POST':
        form = ExamForm(request.user, request.POST)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.user = request.user
            if not exam.category:
                exam.category = get_or_create_default_category(request)
            exam.save()
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
            form.save()
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
            'form': type_form, 'exam': exam,
        })
  
    FormClass, FormSetClass = QUESTION_TYPE_REGISTRY[question_type]
    form = FormClass(request.POST or None)
    formset = FormSetClass(request.POST or None, instance=form.instance) if FormSetClass else None

    if request.method == 'POST':
        # Editor frontend submits custom fields (data_*) — tratar manualmente
        if any(k in request.POST for k in ('data_options', 'data_items', 'data_pairs_left', 'data_front')):
            with transaction.atomic():
                stmt = request.POST.get('statement', '').strip()
                expl = request.POST.get('explanation', '').strip()
                q = None
                if question_type == Question.Types.MULTIPLE_CHOICE:
                    q = MultipleChoiceQuestion(statement=stmt, explanation=expl)
                elif question_type == Question.Types.MULTI_ANSWER:
                    q = MultiAnswerQuestion(statement=stmt, explanation=expl)
                elif question_type == Question.Types.TRUE_FALSE:
                    val = request.POST.get('data_correct', 'false')
                    q = TrueFalseQuestion(statement=stmt, explanation=expl, correct_answer=(val in ('true', '1', 'verdadeiro')))
                elif question_type == Question.Types.WRITTEN:
                    ans = request.POST.get('data_answer', '').strip()
                    q = WrittenQuestion(statement=stmt, explanation=expl, expected_answer=ans)
                elif question_type == Question.Types.ORDERING:
                    q = OrderingQuestion(statement=stmt, explanation=expl)
                elif question_type == Question.Types.MATCHING:
                    q = MatchingQuestion(statement=stmt, explanation=expl)
                elif question_type == Question.Types.FLASHCARD:
                    front = request.POST.get('data_front', '').strip()
                    back = request.POST.get('data_back', '').strip()
                    q = FlashcardQuestion(statement=stmt, explanation=expl, front=front, back=back)

                if q is None:
                    return render(request, 'exams/question_form.html', {
                        'form': form,
                        'formset': formset,
                        'exam': exam,
                        'question_type': question_type,
                        'errors': ['Tipo de questão inválido'],
                        'action': 'add',
                    })

                q.exam = exam
                q.order = exam.questions.count()
                q.save()

                # Criar relacionamentos dependentes do tipo
                if question_type in (Question.Types.MULTIPLE_CHOICE, Question.Types.MULTI_ANSWER):
                    opts = request.POST.getlist('data_options')
                    correct = request.POST.getlist('data_correct')
                    # data_correct for radio may be single value
                    if question_type == Question.Types.MULTIPLE_CHOICE:
                        correct_index = request.POST.get('data_correct')
                        for i, text in enumerate(opts):
                            QuestionOption.objects.create(question=q, text=text.strip(), is_correct=(str(i) == str(correct_index)), order=i)
                    else:
                        correct_set = set(correct)
                        for i, text in enumerate(opts):
                            QuestionOption.objects.create(question=q, text=text.strip(), is_correct=(str(i) in correct_set), order=i)

                if question_type == Question.Types.ORDERING:
                    items = request.POST.getlist('data_items')
                    for pos, text in enumerate(items, start=1):
                        OrderingItem.objects.create(question=q, text=text.strip(), position=pos)

                if question_type == Question.Types.MATCHING:
                    lefts = request.POST.getlist('data_pairs_left')
                    rights = request.POST.getlist('data_pairs_right')
                    for i, (l, r) in enumerate(zip(lefts, rights)):
                        MatchingPair.objects.create(question=q, left=l.strip(), right=r.strip(), order=i)

                # Flashcard, TrueFalse, Written already saved with their fields
                return redirect('exams:edit', pk=exam.pk)

        # Fallback: tentar usar form + formset (ex: admin-like submission)
        form_valid = form.is_valid()
        formset_valid = formset.is_valid() if formset else True
        if form_valid and formset_valid:
            with transaction.atomic():
                question = form.save(commit=False)
                question.exam = exam
                question.order = exam.questions.count()
                question.save()
                if formset:
                    formset.instance = question
                    formset.save()
            return redirect('exams:edit', pk=exam.pk)
  
    # coletar erros de validação para exibir no template
    errors = []
    if request.method == 'POST':
        if form.errors:
            for f, errs in form.errors.items():
                errors.extend([f + ': ' + e for e in errs])
        if formset and formset.errors:
            for fs_err in formset.non_form_errors():
                errors.append(str(fs_err))

    return render(request, 'exams/question_form.html', {
        'form': form,
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
  
    FormClass, FormSetClass = QUESTION_TYPE_REGISTRY[question_type]
  
    form = FormClass(request.POST or None, instance=instance)
    formset = FormSetClass(request.POST or None, instance=instance) if FormSetClass else None
  
    if request.method == 'POST':
        # Editor envia campos customizados (data_*) — tratar atualização manualmente
        if any(k.startswith('data_') for k in request.POST.keys()):
            with transaction.atomic():
                # atualizar campos básicos
                instance.statement = request.POST.get('statement', instance.statement).strip()
                instance.explanation = request.POST.get('explanation', instance.explanation).strip()

                # tipos específicos
                if question_type == Question.Types.MULTIPLE_CHOICE or question_type == Question.Types.MULTI_ANSWER:
                    # atualizar opções existentes ou criar novas conforme necessário
                    opts = request.POST.getlist('data_options')
                    if question_type == Question.Types.MULTIPLE_CHOICE:
                        correct_index = request.POST.get('data_correct')
                    else:
                        correct = set(request.POST.getlist('data_correct'))

                    existing = list(instance.options.order_by('order'))
                    # Atualizar/crear
                    for i, text in enumerate(opts):
                        text = text.strip()
                        if question_type == Question.Types.MULTIPLE_CHOICE:
                            is_correct = (str(i) == str(correct_index))
                        else:
                            is_correct = (str(i) in correct)

                        if i < len(existing):
                            opt = existing[i]
                            opt.text = text
                            opt.is_correct = is_correct
                            opt.order = i
                            opt.save()
                        else:
                            QuestionOption.objects.create(question=instance, text=text, is_correct=is_correct, order=i)

                    # remover quaisquer opções excedentes
                    if len(existing) > len(opts):
                        for extra in existing[len(opts):]:
                            extra.delete()

                if question_type == Question.Types.TRUE_FALSE:
                    val = request.POST.get('data_correct')
                    setattr(instance, 'correct_answer', (val in ('true', '1', 'verdadeiro')))

                if question_type == Question.Types.WRITTEN:
                    setattr(instance, 'expected_answer', request.POST.get('data_answer', getattr(instance, 'expected_answer', '')).strip())

                if question_type == Question.Types.ORDERING:
                    items = request.POST.getlist('data_items')
                    OrderingItem.objects.filter(question=instance).delete()
                    for pos, text in enumerate(items, start=1):
                        OrderingItem.objects.create(question=instance, text=text.strip(), position=pos)

                if question_type == Question.Types.MATCHING:
                    lefts = request.POST.getlist('data_pairs_left')
                    rights = request.POST.getlist('data_pairs_right')
                    MatchingPair.objects.filter(question=instance).delete()
                    for i, (l, r) in enumerate(zip(lefts, rights)):
                        MatchingPair.objects.create(question=instance, left=l.strip(), right=r.strip(), order=i)

                if question_type == Question.Types.FLASHCARD:
                    setattr(instance, 'front', request.POST.get('data_front', getattr(instance, 'front', '')).strip())
                    setattr(instance, 'back', request.POST.get('data_back', getattr(instance, 'back', '')).strip())

                instance.save()
            return redirect('exams:edit', pk=exam.pk)

        # Fallback: validar via form + formset (ex: admin-like submission)
        form_valid = form.is_valid()
        formset_valid = formset.is_valid() if formset else True
        if form_valid and formset_valid:
            with transaction.atomic():
                form.save()
                if formset:
                    formset.save()
            return redirect('exams:edit', pk=exam.pk)
  
    # Construir dados simples para popular o editor via JS
    qdata = {}
    if instance.question_type == 'multiple_choice':
        opts = list(instance.options.order_by('order'))
        qdata = {
            'options': [o.text for o in opts],
            'correct': next((i for i, o in enumerate(opts) if o.is_correct), None),
        }
    elif instance.question_type == 'multi_answer':
        opts = list(instance.options.order_by('order'))
        qdata = {
            'options': [o.text for o in opts],
            'correct': [i for i, o in enumerate(opts) if o.is_correct],
        }
    elif instance.question_type == 'true_false':
        qdata = {'correct': bool(getattr(instance, 'correct_answer', False))}
    elif instance.question_type == 'written':
        qdata = {'answer': getattr(instance, 'expected_answer', '')}
    elif instance.question_type == 'ordering':
        qdata = {'items': [it.text for it in instance.items.order_by('position')]}
    elif instance.question_type == 'matching':
        qdata = {'pairs': [{'left': p.left, 'right': p.right} for p in instance.pairs.order_by('order')]}
    elif instance.question_type == 'flashcard':
        qdata = {'front': getattr(instance, 'front', ''), 'back': getattr(instance, 'back', '')}

    return render(request, 'exams/question_form.html', {
        'form': form,
        'formset': formset,
        'exam': exam,
        'question': instance,
        'question_data_json': json.dumps(qdata),
        'question_type': question_type,
        'action': 'edit',
    })


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