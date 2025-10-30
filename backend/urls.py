from django.urls import path
from . import views

app_name = 'backend'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('api/login/', views.api_login, name='api_login'),
    path('api/ingest/', views.api_ingest, name='api_ingest'),
]
