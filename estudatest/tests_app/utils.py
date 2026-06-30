from categories.models import Category

def get_or_create_default_category(request):
    category, _ = Category.objects.get_or_create(
        user=request.user, 
        name='~ sem categoria'
    )
    return category