from django.shortcuts import render

# Create your views here.
# core/views.py
from django.contrib.auth.views import LoginView, LogoutView
from .forms import StaffAuthenticationForm  # ruta según donde lo colocaste
from django.urls import reverse_lazy

class AdminLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = StaffAuthenticationForm
    redirect_authenticated_user = True
    # Si quieres que tras login vaya a dashboard:
    next_page = reverse_lazy('inicio')  # opcional, LoginView usa setting LOGIN_REDIRECT_URL

class AdminLogoutView(LogoutView):
    next_page = reverse_lazy('inicio')  # o '/' o el nombre de la vista de inicio
