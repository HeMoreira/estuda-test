import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Count, Prefetch
from tests_app.models import Test
from tests_app.spaced_repetition import get_urgency_ratio, urgency_color
from attempts.models import Attempt
from .models import Category
from .forms import CategoryForm


@login_required
def dashboard(request):
    categories = Category.objects.filter(user=request.user).prefetch_related(
        Prefetch('tests', queryset=Test.objects.filter(user=request.user).prefetch_related('attempts'))
    )

    categories_with_tests = []
    for cat in categories:
        tests_data = []
        for test in cat.tests.all():
            last_attempt = test.attempts.order_by('-started_at').first()
            attempt_count = test.attempts.count()
            ratio = get_urgency_ratio(attempt_count, last_attempt.started_at if last_attempt else None)
            color = urgency_color(ratio)
            tests_data.append({
                'test': test,
                'last_attempt': last_attempt,
                'urgency_ratio': ratio,
                'urgency_color': color,
                'question_count': test.question_count(),
            })
        if tests_data:
            categories_with_tests.append({'category': cat, 'tests': tests_data})

    uncategorized = Test.objects.filter(user=request.user, category__isnull=True)
    uncategorized_data = []
    for test in uncategorized:
        last_attempt = test.attempts.order_by('-started_at').first()
        attempt_count = test.attempts.count()
        ratio = get_urgency_ratio(attempt_count, last_attempt.started_at if last_attempt else None)
        color = urgency_color(ratio)
        uncategorized_data.append({
            'test': test,
            'last_attempt': last_attempt,
            'urgency_ratio': ratio,
            'urgency_color': color,
            'question_count': test.question_count(),
        })

    has_any = categories.exists() or uncategorized.exists()
    return render(request, 'categories/dashboard.html', {
        'categories_with_tests': categories_with_tests,
        'uncategorized_data': uncategorized_data,
        'has_any': has_any,
        'all_categories': Category.objects.filter(user=request.user),
    })


@login_required
@require_POST
def category_create(request):
    form = CategoryForm(request.POST)
    if form.is_valid():
        cat = form.save(commit=False)
        cat.user = request.user
        cat.save()
        return JsonResponse({'ok': True, 'id': cat.id, 'name': cat.name})
    return JsonResponse({'ok': False, 'errors': form.errors}, status=400)


@login_required
@require_http_methods(['DELETE'])
def category_delete(request, pk):
    cat = get_object_or_404(Category, pk=pk, user=request.user)
    cat.delete()
    return JsonResponse({'ok': True})
