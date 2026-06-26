from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('categories/', include('categories.urls')),
    path('tests/', include('tests_app.urls')),
    path('attempts/', include('attempts.urls')),
    path('', include('categories.urls_dashboard')),
]
