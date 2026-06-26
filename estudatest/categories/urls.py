from django.urls import path
from . import views

app_name = 'categories'

urlpatterns = [
    path('create/', views.category_create, name='create'),
    path('<int:pk>/delete/', views.category_delete, name='delete'),
]
