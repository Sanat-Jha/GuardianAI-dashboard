from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # web views
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password-reset/', views.password_reset_info, name='password_reset'),
    path('child/<str:child_hash>/upload-profile-image/', views.upload_child_profile_image, name='upload_child_profile_image'),
]
