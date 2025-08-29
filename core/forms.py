# core/forms.py

from django import forms
from .models import Cliente, Vendedor

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
