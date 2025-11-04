from django.urls import path
from . import views

app_name = 'backend'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/chart-data/<str:child_hash>/', views.child_chart_data, name='child_chart_data'),
    path('dashboard/stats/<str:child_hash>/', views.child_stats_data, name='child_stats_data'),
    path('dashboard/locations/<str:child_hash>/', views.child_locations_data, name='child_locations_data'),
    path('dashboard/site-logs/<str:child_hash>/', views.child_site_logs_data, name='child_site_logs_data'),
    path('api/login/', views.api_login, name='api_login'),
    path('api/ingest/', views.api_ingest, name='api_ingest'),
]
