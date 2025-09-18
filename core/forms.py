# core/forms.py

from django import forms
from .models import Cliente, Vendedor
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User

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
    # Campos para edición de credenciales (solo se muestran en edición)
    nombre_usuario = forms.CharField(
        max_length=150,
        required=False,
        label="Nombre de usuario"
    )
    nueva_contraseña = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        label="Nueva contraseña (dejar vacío para no cambiar)"
    )

    class Meta:
        model = Vendedor
        fields = ['nombre_completo', 'sexo', 'nacionalidad',
                  'domicilio', 'ine', 'telefono', 'email', 'tipo']
        widgets = {
            'domicilio': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Si estamos editando un vendedor existente con usuario
        if self.instance and self.instance.pk and self.instance.usuario:
            # Mostrar y hacer requerido el campo de nombre de usuario
            self.fields['nombre_usuario'].initial = self.instance.usuario.username
            self.fields['nombre_usuario'].required = True
        else:
            # Ocultar campos de credenciales en creación
            self.fields['nombre_usuario'].widget = forms.HiddenInput()
            self.fields['nueva_contraseña'].widget = forms.HiddenInput()

    def clean_nombre_usuario(self):
        nombre_usuario = self.cleaned_data.get('nombre_usuario')
        
        # Solo validar si estamos editando y el campo es visible
        if self.instance and self.instance.pk and self.instance.usuario and nombre_usuario:
            # Verificar que el nombre de usuario no esté en uso (excluyendo el usuario actual)
            if User.objects.filter(username=nombre_usuario).exclude(id=self.instance.usuario.id).exists():
                raise forms.ValidationError("Este nombre de usuario ya está en uso.")
        
        return nombre_usuario

    def save(self, commit=True):
        vendedor = super().save(commit=False)
        
        # Si estamos editando un vendedor existente con usuario
        if vendedor.usuario and self.cleaned_data.get('nombre_usuario'):
            # Actualizar nombre de usuario si cambió
            if vendedor.usuario.username != self.cleaned_data['nombre_usuario']:
                vendedor.usuario.username = self.cleaned_data['nombre_usuario']
                vendedor.usuario.save()
            
            # Actualizar contraseña si se proporcionó una nueva
            if self.cleaned_data.get('nueva_contraseña'):
                vendedor.usuario.set_password(self.cleaned_data['nueva_contraseña'])
                vendedor.usuario.save()
                # Actualizar la contraseña temporal
                vendedor.contraseña_temporal = self.cleaned_data['nueva_contraseña']
        
        if commit:
            vendedor.save()
        
        return vendedor

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
        # Verificar si el usuario es staff o tiene un perfil de vendedor asociado
        if not (user.is_active and (user.is_staff or hasattr(user, 'vendedor'))):
            raise forms.ValidationError(
                "Acceso denegado: debes ser usuario del staff o vendedor autorizado para iniciar sesión aquí.",
                code='invalid_login',
            )

