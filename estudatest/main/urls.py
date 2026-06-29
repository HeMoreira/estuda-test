from django.urls import path
from main.views import dashboard

urlpatterns = [
    path('', dashboard, name='dashboard'),
]
