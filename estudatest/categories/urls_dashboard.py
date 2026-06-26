from django.urls import path
from categories.views import dashboard

urlpatterns = [
    path('', dashboard, name='dashboard'),
]
