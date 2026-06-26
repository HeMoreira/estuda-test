from django.urls import path
from . import views

app_name = 'tests_app'

urlpatterns = [
    path('create/', views.test_create, name='create'),
    path('<int:pk>/edit/', views.test_edit, name='edit'),
    path('<int:pk>/detail/', views.test_detail_json, name='detail_json'),
    path('<int:pk>/delete/', views.test_delete, name='delete'),
    path('<int:test_pk>/questions/add/', views.question_add, name='question_add'),
    path('<int:test_pk>/questions/<int:pk>/edit/', views.question_edit, name='question_edit'),
    path('<int:test_pk>/questions/<int:pk>/delete/', views.question_delete, name='question_delete'),
]
