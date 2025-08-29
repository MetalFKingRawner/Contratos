# dashboard/forms.py
from django import forms
from core.models import Propietario, Proyecto, Lote, Cliente, Vendedor

from workflow.models import Tramite, ClausulasEspeciales
from financiamiento.models import Financiamiento


class PropietarioForm(forms.ModelForm):
    class Meta:
        model = Propietario
        fields = [
            'proyecto', 'nombre_completo', 'sexo', 'nacionalidad',
            'domicilio', 'ine', 'telefono', 'email',
            'tipo', 'instrumento_publico', 'notario_publico', 'nombre_notario'
        ]
        widgets = {
            'proyecto': forms.Select(attrs={'class': 'form-select'}),
            'domicilio': forms.Textarea(attrs={'rows': 2}),
            'telefono': forms.TextInput(attrs={'placeholder': '9511234567'}),
            'email': forms.EmailInput(),
        }

class ProyectoForm(forms.ModelForm):
    class Meta:
        model = Proyecto
        fields = ['nombre', 'tipo_contrato', 'ubicacion', 'fecha_emision_documento', 'autoridad', 'fecha_emision_contrato']
        widgets = {
            'ubicacion': forms.Textarea(attrs={'rows': 2}),
            'fecha_emision_documento': forms.TextInput(attrs={'placeholder': 'DD/MM/AAAA o texto'}),
            'fecha_emision_contrato': forms.TextInput(attrs={'placeholder': 'DD/MM/AAAA o texto'}),
        }

class LoteForm(forms.ModelForm):
    class Meta:
        model = Lote
        fields = ["proyecto", "identificador", "norte", "sur", "este", "oeste", "manzana", "activo"]
        widgets = {
            "proyecto": forms.Select(attrs={"class": "form-select"}),
            "identificador": forms.TextInput(attrs={"class": "form-control"}),
            "norte": forms.TextInput(attrs={"class": "form-control"}),
            "sur": forms.TextInput(attrs={"class": "form-control"}),
            "este": forms.TextInput(attrs={"class": "form-control"}),
            "oeste": forms.TextInput(attrs={"class": "form-control"}),
            "manzana": forms.TextInput(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

class ClausulasEspecialesForm(forms.ModelForm):
    """Formulario para las cláusulas especiales del trámite"""
    class Meta:
        model = ClausulasEspeciales
        fields = ['clausula_pago', 'clausula_deslinde', 'clausula_promesa']
        widgets = {
            'clausula_pago': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4,
                'placeholder': 'Ingrese la cláusula de pago personalizada...'
            }),
            'clausula_deslinde': forms.Textarea(attrs={
                'class': 'form-textarea', 
                'rows': 4,
                'placeholder': 'Ingrese la cláusula de deslinde personalizada...'
            }),
            'clausula_promesa': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 4, 
                'placeholder': 'Ingrese la cláusula de promesa personalizada...'
            }),
        }

class TramiteForm(forms.ModelForm):
    class Meta:
        model = Tramite
        fields = [
            'financiamiento', 
            'cliente', 
            'vendedor', 
            'firma_cliente',
            'cliente_2'
        ]
        widgets = {
            'financiamiento': forms.Select(attrs={
                'class': 'form-select',
                'hx-get': '',  # Puedes añadir funcionalidad HTMX si necesitas
                'hx-target': '#id_cliente'
            }),
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'vendedor': forms.Select(attrs={'class': 'form-select'}),
            'cliente_2': forms.Select(attrs={'class': 'form-select'}),
            'firma_cliente': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personalizar las querysets si es necesario
        self.fields['financiamiento'].queryset = Financiamiento.objects.all()
        self.fields['cliente'].queryset = Cliente.objects.all()
        self.fields['vendedor'].queryset = Vendedor.objects.all()
        self.fields['cliente_2'].queryset = Cliente.objects.all()
        
        # Hacer que el campo cliente_2 no sea requerido
        self.fields['cliente_2'].required = False

        # Inicializar el formulario de cláusulas especiales
        if self.instance and self.instance.pk:
            # Si es una edición, obtener las cláusulas existentes
            try:
                clausulas_instance = self.instance.clausulas_especiales
            except ClausulasEspeciales.DoesNotExist:
                clausulas_instance = ClausulasEspeciales(tramite=self.instance)
        else:
            # Si es nuevo, crear instancia vacía
            clausulas_instance = None

        self.clausulas_form = ClausulasEspecialesForm(
            data=self.data or None,
            instance=clausulas_instance,
            prefix='clausulas'
        )

    def is_valid(self):
        # Validar ambos formularios
        is_valid = super().is_valid()
        is_valid = is_valid and self.clausulas_form.is_valid()
        return is_valid

    def save(self, commit=True):
        # Guardar el trámite primero
        tramite = super().save(commit=commit)
        
        # Guardar las cláusulas especiales
        clausulas = self.clausulas_form.save(commit=False)
        clausulas.tramite = tramite
        if commit:
            clausulas.save()
            
        return tramite