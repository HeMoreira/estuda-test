import json
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from .models import Category
from .forms import CategoryForm

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
