from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch

from categories.models import Category
from exams.models import Exam
from exams.spaced_repetition import get_urgency_ratio, urgency_color

# Create your views here.
@login_required
def dashboard(request):
    categories = Category.objects.filter(user=request.user).prefetch_related(
        Prefetch('exams', queryset=Exam.objects.filter(user=request.user).prefetch_related('attempts'))
    )

    categories_with_exams = []
    for cat in categories:
        exams_data = []
        for exam in cat.exams.all():
            last_attempt = exam.attempts.order_by('-started_at').first()
            attempt_count = exam.attempts.count()
            ratio = get_urgency_ratio(attempt_count, last_attempt.started_at if last_attempt else None)
            color = urgency_color(ratio)
            exams_data.append({
                'exam': exam,
                'last_attempt': last_attempt,
                'urgency_ratio': ratio,
                'urgency_color': color,
                'question_count': exam.question_count(),
            })
        if exams_data:
            categories_with_exams.append({'category': cat, 'exams': exams_data})

    has_any = categories.exists()
    return render(request, 'main/dashboard.html', {
        'categories_with_exams': categories_with_exams,
        'has_any': has_any,
        'all_categories': Category.objects.filter(user=request.user),
    })