# pagos/forms.py
from django import forms
from django.utils import timezone
from .models import Pago

# pagos/forms.py - Corregir formulario
# pagos/forms.py
from django import forms
from django.utils import timezone
from .models import Pago

# pagos/forms.py - Actualizar RegistroPagoForm
class RegistroPagoForm(forms.ModelForm):
    # Campos adicionales para manejo de saldo y excedente
    usar_saldo_disponible = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'usar_saldo_checkbox'
        }),
        label="Usar saldo a favor disponible"
    )
    
    monto_saldo_usar = forms.DecimalField(
        required=False,
        initial=0,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'disabled': 'disabled',
            'id': 'monto_saldo_input'
        }),
        label="Monto de saldo a usar"
    )
    
    manejo_excedente = forms.ChoiceField(
        required=False,
        initial='saldo_favor',
        choices=[
            ('saldo_favor', 'Crear saldo a favor'),
            ('aplicar_proxima', 'Aplicar a próxima cuota'),
            ('dividir', 'Dividir entre ambas opciones'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label="Manejo de excedente"
    )
    
    monto_aplicar_proxima = forms.DecimalField(
        required=False,
        initial=0,
        max_digits=10,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'disabled': 'disabled',
            'id': 'monto_aplicar_input'
        }),
        label="Monto a aplicar a próxima cuota"
    )
    
    class Meta:
        model = Pago
        fields = ['fecha_pago', 'monto_pagado', 'metodo_pago', 'observaciones']
        widgets = {
            'fecha_pago': forms.DateInput(
                attrs={
                    'type': 'date', 
                    'class': 'form-control',
                    'required': 'required'
                }
            ),
            'monto_pagado': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'min': '0',
                    'step': '0.01',
                    'required': 'required',
                    'id': 'monto_pagado_input'
                }
            ),
            'metodo_pago': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
            'observaciones': forms.Textarea(
                attrs={
                    'rows': 3, 
                    'class': 'form-control',
                    'placeholder': 'Observaciones del pago...'
                }
            ),
        }
    
    def __init__(self, *args, **kwargs):
        self.pago = kwargs.pop('pago', None)
        self.saldo_disponible = kwargs.pop('saldo_disponible', 0)
        super().__init__(*args, **kwargs)
        
        if self.pago:
            monto_faltante = self.pago.monto - self.pago.monto_pagado
            self.fields['monto_pagado'].widget.attrs['min'] = str(0.01)
            self.fields['monto_pagado'].widget.attrs['placeholder'] = f"Mínimo: ${monto_faltante:.2f}"
            
            if not self.instance.pk and not self.initial.get('fecha_pago'):
                self.initial['fecha_pago'] = timezone.now().date()
            
            # Configurar límite para monto de saldo a usar
            if self.saldo_disponible > 0:
                self.fields['monto_saldo_usar'].widget.attrs['max'] = str(min(
                    self.saldo_disponible,
                    monto_faltante
                ))
                self.fields['monto_saldo_usar'].initial = min(
                    self.saldo_disponible,
                    monto_faltante
                )
        
        self.fields['metodo_pago'].choices = [
            ('', 'Seleccionar método'),
            ('efectivo', 'Efectivo'),
            ('transferencia', 'Transferencia'),
            ('cheque', 'Cheque'),
            ('tarjeta', 'Tarjeta de crédito/débito'),
            ('deposito', 'Depósito bancario'),
            ('otros', 'Otros'),
        ]
    
    def clean(self):
        cleaned_data = super().clean()
        monto_pagado = cleaned_data.get('monto_pagado', 0)
        usar_saldo = cleaned_data.get('usar_saldo_disponible', False)
        monto_saldo_usar = cleaned_data.get('monto_saldo_usar', 0)
        manejo_excedente = cleaned_data.get('manejo_excedente', 'saldo_favor')
        monto_aplicar_proxima = cleaned_data.get('monto_aplicar_proxima', 0)
        
        if self.pago:
            monto_faltante = self.pago.monto - self.pago.monto_pagado
            
            # Validar uso de saldo
            if usar_saldo and monto_saldo_usar > 0:
                if monto_saldo_usar > self.saldo_disponible:
                    self.add_error('monto_saldo_usar', 
                                 f"No puedes usar más de ${self.saldo_disponible:.2f} en saldo")
                
                if monto_saldo_usar > monto_faltante:
                    self.add_error('monto_saldo_usar',
                                 f"No necesitas más de ${monto_faltante:.2f} para completar esta cuota")
            
            # Validar manejo de excedente
            if manejo_excedente == 'dividir' and monto_aplicar_proxima <= 0:
                self.add_error('monto_aplicar_proxima',
                             "Debes especificar un monto a aplicar a la próxima cuota")
            
            monto_total = monto_pagado + (monto_saldo_usar if usar_saldo else 0)
            
            # Si el monto total es menor al faltante, es un pago parcial (está permitido)
            # Si es mayor, validar que no sea excesivo (máximo 2 veces el monto de la cuota)
            if monto_total > monto_faltante * 2:
                self.add_error('monto_pagado',
                             f"El pago no puede superar el doble del monto pendiente (${monto_faltante * 2:.2f})")
        
        return cleaned_data
    
    def clean_monto_pagado(self):
        monto_pagado = self.cleaned_data['monto_pagado']
        if monto_pagado <= 0:
            raise forms.ValidationError("El monto pagado debe ser mayor a 0")
        return monto_pagado
    
    def clean_fecha_pago(self):
        fecha_pago = self.cleaned_data['fecha_pago']
        if fecha_pago > timezone.now().date():
            raise forms.ValidationError("La fecha de pago no puede ser futura")
        return fecha_pago
    
# pagos/forms.py - Agregar este formulario
class AplicarSaldoFavorForm(forms.Form):
    """Formulario para aplicar saldo a favor a cuotas específicas"""
    
    def __init__(self, *args, **kwargs):
        self.tramite = kwargs.pop('tramite', None)
        self.saldo_disponible = kwargs.pop('saldo_disponible', 0)
        super().__init__(*args, **kwargs)
        
        if self.tramite and self.saldo_disponible > 0:
            # Obtener cuotas pendientes o parciales
            pagos = self.tramite.pagos.filter(
                estado__codigo__in=['pendiente', 'parcial']
            ).order_by('numero_cuota')
            
            for pago in pagos:
                field_name = f'pago_{pago.id}'
                self.fields[field_name] = forms.DecimalField(
                    required=False,
                    max_digits=10,
                    decimal_places=2,
                    min_value=0,
                    max_value=min(self.saldo_disponible, pago.monto - pago.monto_pagado),
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control aplicar-saldo-input',
                        'placeholder': '0.00',
                        'data-pago-id': pago.id,
                        'data-monto-max': pago.monto - pago.monto_pagado
                    }),
                    label=f"Cuota #{pago.numero_cuota} - ${pago.monto - pago.monto_pagado:.2f} pendiente"
                )
    
    def clean(self):
        cleaned_data = super().clean()
        total_aplicado = 0
        
        for field_name, value in cleaned_data.items():
            if field_name.startswith('pago_') and value:
                total_aplicado += value
        
        if total_aplicado > self.saldo_disponible:
            raise forms.ValidationError(
                f"No puedes aplicar más de ${self.saldo_disponible:.2f} en total"
            )
        
        return cleaned_data