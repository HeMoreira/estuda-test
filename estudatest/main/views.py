from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch

from categories.models import Category
from tests_app.models import Test
from tests_app.spaced_repetition import get_urgency_ratio, urgency_color

# Create your views here.
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
    return render(request, 'main/dashboard.html', {
        'categories_with_tests': categories_with_tests,
        'uncategorized_data': uncategorized_data,
        'has_any': has_any,
        'all_categories': Category.objects.filter(user=request.user),
    })