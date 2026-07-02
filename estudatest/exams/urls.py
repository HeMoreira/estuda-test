from django.urls import path
from . import views

app_name = 'exams'

urlpatterns = [
    path('create/', views.exam_create, name='create'),
    path('<int:pk>/edit/', views.exam_edit, name='edit'),
    path('<int:pk>/detail/', views.exam_detail_json, name='detail_json'),
    path('<int:pk>/delete/', views.exam_delete, name='delete'),
    path('<int:exam_pk>/questions/add/', views.question_add, name='question_add'),
    path('<int:exam_pk>/questions/<int:pk>/edit/', views.question_edit, name='question_edit'),
    path('<int:exam_pk>/questions/<int:pk>/delete/', views.question_delete, name='question_delete'),
]
