# financiamiento/forms.py

from django import forms
from .models import Financiamiento

class FinanciamientoForm(forms.ModelForm):
    class Meta:
        model = Financiamiento
        fields = [
            'nombre_cliente', 'lote', 'tipo_pago',
            'precio_lote', 'apartado',
            'fecha_pago_completo', 'monto_pago_completo',
            'enganche', 'fecha_enganche',
            'num_mensualidades', 'monto_mensualidad',
            'fecha_primer_pago', 'fecha_ultimo_pago','monto_pago_final',
        ]
        widgets = {
            'fecha_pago_completo': forms.DateInput(attrs={'type': 'date'}),
            'fecha_enganche':      forms.DateInput(attrs={'type': 'date'}),
            'fecha_primer_pago':   forms.DateInput(attrs={'type': 'date'}),
            'fecha_ultimo_pago':   forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Campos que sólo validaremos en clean()
        opcionales = [
            'fecha_pago_completo', 'monto_pago_completo',
            'enganche', 'fecha_enganche',
            'num_mensualidades', 'monto_mensualidad',
            'fecha_primer_pago', 'fecha_ultimo_pago',
        ]
        for field in opcionales:
            self.fields[field].required = False

    def clean(self):
        cd = super().clean()
        tipo = cd.get('tipo_pago')

        if tipo == 'contado':
            if not cd.get('fecha_pago_completo') or cd.get('monto_pago_completo') is None:
                raise forms.ValidationError(
                    "Para pago de contado debes especificar fecha y monto del pago completo."
                )
        elif tipo == 'financiado':
            if cd.get('apartado') is None or cd.get('enganche') is None:
                raise forms.ValidationError(
                    "Para financiamiento debes especificar apartado y enganche."
                )
            if not cd.get('fecha_enganche'):
                raise forms.ValidationError("Debes indicar la fecha de enganche.")
            if not cd.get('num_mensualidades'):
                raise forms.ValidationError("Debes indicar el número de mensualidades.")
            if cd.get('monto_mensualidad') is None:
                raise forms.ValidationError("Debes indicar el monto de la mensualidad fija.")
        else:
            raise forms.ValidationError("Selecciona un tipo de pago válido.")

        return cd