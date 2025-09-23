from django.urls import path
from django.contrib.auth import views as auth_views # Django's built-in auth views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='tiffin_app/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'), # Redirect to home after logout
]