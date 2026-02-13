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
    def get_success_url(self):
        """
        Redirige según el tipo de usuario:
        - Usuario de Contabilidad (no staff) -> Dashboard de Pagos
        - Usuario staff u otros -> Inicio
        """
        user = self.request.user
        
        # Verificar si el usuario pertenece al grupo "Contabilidad" y NO es staff
        if user.groups.filter(name="Contabilidad").exists():
            return reverse_lazy('pagos:dashboard')
        
        # Para staff y otros usuarios, ir a inicio
        return reverse_lazy('inicio')

class AdminLogoutView(LogoutView):
    next_page = reverse_lazy('inicio')  # o '/' o el nombre de la vista de inicio
