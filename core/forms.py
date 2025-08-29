# core/forms.py

from django import forms
from .models import Cliente, Vendedor
from django.contrib.auth.forms import AuthenticationForm

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'nombre_completo',
            'sexo',
            'rfc',
            'domicilio',
            'telefono',
            'email',
            'ocupacion',
            'estado_civil',
            'nacionalidad',
            'originario',
            'tipo_id',
            'numero_id',
        ]
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'sexo': forms.Select(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'tipo_id': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_id': forms.TextInput(attrs={'class': 'form-control'}),
            'rfc': forms.TextInput(attrs={'class': 'form-control'}),
            'nacionalidad': forms.TextInput(attrs={'class': 'form-control'}),
            'originario': forms.TextInput(attrs={'class': 'form-control'}),
            'estado_civil': forms.TextInput(attrs={'class': 'form-control'}),
            'ocupacion': forms.TextInput(attrs={'class': 'form-control'}),
            'domicilio': forms.Textarea(attrs={'rows': 2}),
        }

class VendedorForm(forms.ModelForm):
    class Meta:
        model = Vendedor
        fields = ['nombre_completo', 'sexo', 'nacionalidad',
                  'domicilio', 'ine', 'telefono', 'email', 'tipo']
        widgets = {
            'domicilio': forms.Textarea(attrs={'rows':2}),
        }

class StaffAuthenticationForm(AuthenticationForm):
    """
    Extiende el formulario de autenticación para:
    - Rechazar usuarios que no sean staff (is_staff).
    - Añadir atributos de widget (clase CSS) a los campos.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Añadimos clases y placeholders a los widgets
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Usuario'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Contraseña'
        })

    def confirm_login_allowed(self, user):
        # Reusa la validación del parent para is_active etc. (AuthenticationForm ya maneja is_active)
        if not (user.is_active and user.is_staff):
            raise forms.ValidationError(
                "Acceso denegado: debes ser usuario del staff para iniciar sesión aquí.",
                code='invalid_login',
            )
