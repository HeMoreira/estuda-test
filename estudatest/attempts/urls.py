from django.urls import path
from . import views

app_name = 'attempts'

urlpatterns = [
    path('start/<int:exam_pk>/', views.attempt_start, name='start'),
    path('<int:attempt_id>/question/<int:n>/', views.attempt_question, name='question'),
    path('<int:attempt_id>/review/', views.attempt_review, name='review'),
]
