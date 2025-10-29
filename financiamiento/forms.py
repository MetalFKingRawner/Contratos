# financiamiento/forms.py

from django import forms
from core.models import Proyecto, Lote
from .models import Financiamiento

class FinanciamientoForm(forms.ModelForm):
    proyecto = forms.ModelChoiceField(
        queryset=Proyecto.objects.all(),
        label="Lotificación",
        required=True
    )
    lote = forms.ModelChoiceField(
        queryset=Lote.objects.none(),  # se llenará en __init__
        label="Lote",
        required=True
    )
    
    class Meta:
        model = Financiamiento
        fields = [
            'nombre_cliente','proyecto','lote','tipo_pago',
            'precio_lote','apartado',
            'fecha_pago_completo','monto_pago_completo',
            'enganche','fecha_enganche',
            'num_mensualidades','monto_mensualidad',
            'fecha_primer_pago','fecha_ultimo_pago','monto_pago_final',
            'es_cotizacion', 'activo'  # NUEVOS CAMPOS AÑADIDOS
        ]
        widgets = {
            # ¡OJO! aquí forzamos text en lugar de number:
            'precio_lote':        forms.TextInput(attrs={'type': 'text'}),
            'apartado':           forms.TextInput(attrs={'type': 'text'}),
            'monto_pago_completo':forms.TextInput(attrs={'type': 'text'}),
            'enganche':           forms.TextInput(attrs={'type': 'text'}),
            'monto_mensualidad':  forms.TextInput(attrs={'type': 'text'}),
            # Los dateInput se quedan igual:
            'fecha_pago_completo': forms.DateInput(attrs={'type': 'date'}),
            'fecha_enganche':      forms.DateInput(attrs={'type': 'date'}),
            'fecha_primer_pago':   forms.DateInput(attrs={'type': 'date'}),
            'fecha_ultimo_pago':   forms.DateInput(attrs={'type': 'date'}),
            # NUEVOS CAMPOS - checkboxes
            'es_cotizacion': forms.CheckboxInput(attrs={'class': 'checkbox-field'}),
            'activo': forms.CheckboxInput(attrs={'class': 'checkbox-field'}),
        }
        help_texts = {
            'es_cotizacion': 'Marcar si es solo una cotización/presupuesto, no un financiamiento real',
            'activo': 'Desmarcar para desactivar este plan',
        }

    def __init__(self, *args, **kwargs):
        # 💡 CORRECCIÓN: Establecer valores iniciales ANTES de super().__init__
        instance = kwargs.get('instance')
        if instance and instance.pk:
            # Pre-inicializar kwargs para las fechas
            if not kwargs.get('initial'):
                kwargs['initial'] = {}
            
            # Establecer formato YYYY-MM-DD para campos de fecha
            date_fields = ['fecha_pago_completo', 'fecha_enganche', 'fecha_primer_pago', 'fecha_ultimo_pago']
            for field_name in date_fields:
                field_value = getattr(instance, field_name, None)
                if field_value:
                    kwargs['initial'][field_name] = field_value.strftime('%Y-%m-%d')
            
            # También para campos de dinero
            money_fields = ['precio_lote', 'apartado', 'monto_pago_completo', 'enganche', 'monto_mensualidad']
            for field_name in money_fields:
                field_value = getattr(instance, field_name, None)
                if field_value is not None:
                    kwargs['initial'][field_name] = str(field_value)
        
        super().__init__(*args, **kwargs)
        
        # Resto de la lógica de inicialización...
        if self.instance and self.instance.lote_id:
            lote_actual = self.instance.lote
            if not lote_actual.activo:
                lote_actual.activo = True
                lote_actual.save()
            proj = self.instance.lote.proyecto
            self.fields['proyecto'].initial = proj
            self.fields['lote'].queryset = Lote.objects.filter(proyecto=proj, activo=True)
            self.fields['lote'].initial = lote_actual
        elif 'proyecto' in self.data:
            try:
                proj_id = int(self.data.get('proyecto'))
                self.fields['lote'].queryset = Lote.objects.filter(proyecto_id=proj_id, activo=True)
            except (ValueError, TypeError):
                pass
        else:
            self.fields['lote'].queryset = Lote.objects.none()
        
        # Campos opcionales
        opcionales = [
            'fecha_pago_completo', 'monto_pago_completo',
            'enganche', 'fecha_enganche',
            'num_mensualidades', 'monto_mensualidad',
            'fecha_primer_pago', 'fecha_ultimo_pago',
            'es_cotizacion', 'activo'  # Los nuevos campos son opcionales en el formulario
        ]
        for field in opcionales:
            self.fields[field].required = False

        # Establecer valores por defecto para nuevos campos si es un nuevo registro
        if not instance:
            self.fields['es_cotizacion'].initial = False
            self.fields['activo'].initial = True

        # NUEVA LÓGICA: Si es pago de contado, forzar es_cotizacion a False
        if self.instance and self.instance.pk:
            # Si estamos editando y el tipo de pago es contado, desmarcar cotización
            if self.instance.tipo_pago == 'contado':
                self.fields['es_cotizacion'].initial = False
        else:
            # Si es nuevo, inicializar según el tipo de pago
            tipo_pago_initial = self.initial.get('tipo_pago')
            if tipo_pago_initial == 'contado':
                self.fields['es_cotizacion'].initial = False

    def clean(self):
        cd = super().clean()
        tipo = cd.get('tipo_pago')
        es_cotizacion = cd.get('es_cotizacion', False)

        # NUEVA VALIDACIÓN: Cotización solo aplica para financiado
        if tipo == 'contado' and es_cotizacion:
            raise forms.ValidationError(
                "Las cotizaciones solo están disponibles para pagos financiados, no para pagos de contado."
            )

        # Si es cotización, las validaciones son más flexibles
        if es_cotizacion:
            # Para cotizaciones, solo validamos campos básicos
            if not cd.get('nombre_cliente'):
                raise forms.ValidationError("Para una cotización, el nombre del cliente es obligatorio.")
            if not cd.get('lote'):
                raise forms.ValidationError("Para una cotización, debe seleccionar un lote.")
            if not cd.get('precio_lote'):
                raise forms.ValidationError("Para una cotización, el precio del lote es obligatorio.")
        else:
            # Para financiamientos reales, aplicamos todas las validaciones originales
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

class CartaIntencionForm(forms.ModelForm):
    financiamiento = forms.ModelChoiceField(
        queryset=Financiamiento.objects.all(),
        label="Financiamiento relacionado",
        required=True
    )
    vendedor = forms.ModelChoiceField(
        queryset=Vendedor.objects.all(),
        label="Vendedor/Asesor",
        required=True
    )
    
    class Meta:
        model = CartaIntencion
        fields = [
            'financiamiento', 'vendedor',
            'nombre_cliente', 'domicilio', 'tipo_id', 'numero_id',
            'telefono_cliente', 'correo_cliente', 'oferta', 'forma_pago',
            'credito_hipotecario', 'institucion_financiera', 'destinatario_apartado'
        ]
        widgets = {
            'nombre_cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'domicilio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tipo_id': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_id': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono_cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'correo_cliente': forms.EmailInput(attrs={'class': 'form-control'}),
            'oferta': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'forma_pago': forms.Select(attrs={'class': 'form-control'}),
            'credito_hipotecario': forms.Select(attrs={'class': 'form-control'}),
            'institucion_financiera': forms.TextInput(attrs={'class': 'form-control'}),
            'destinatario_apartado': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'numero_id': 'Número de identificación',
            'telefono_cliente': 'Teléfono',
            'correo_cliente': 'Correo electrónico',
            'oferta': 'Oferta de compra ($)',
            'forma_pago': 'Forma de pago preferida',
            'credito_hipotecario': '¿Requiere crédito hipotecario?',
            'institucion_financiera': 'Institución financiera (si aplica)',
            'destinatario_apartado': 'Destinatario del apartado',
        }
        help_texts = {
            'institucion_financiera': 'Solo completar si selecciona "Sí" en crédito hipotecario',
            'destinatario_apartado': 'Persona que recibirá el apartado (por defecto se usará el nombre del vendedor)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Precargar datos si tenemos una instancia existente
        if self.instance and self.instance.pk:
            # Precaragar datos del financiamiento relacionado
            fin = self.instance.financiamiento
            if fin:
                # Precargar datos del cliente desde el financiamiento si están vacíos
                if not self.instance.nombre_cliente:
                    self.fields['nombre_cliente'].initial = fin.nombre_cliente
                
                # Precargar oferta con el precio del lote si está vacía
                if not self.instance.oferta:
                    self.fields['oferta'].initial = fin.precio_lote
                
                # Precargar destinatario con nombre del vendedor si está vacío
                if not self.instance.destinatario_apartado and self.instance.vendedor:
                    self.fields['destinatario_apartado'].initial = self.instance.vendedor.nombre_completo
        
        # Si es un nuevo registro (sin instancia)
        elif not self.instance.pk:
            # Establecer valores por defecto
            self.fields['tipo_id'].initial = 'INE'
            self.fields['forma_pago'].initial = 'Efectivo'
            self.fields['credito_hipotecario'].initial = 'No'
            
            # Si se pasa un financiamiento específico en los parámetros iniciales
            if 'financiamiento' in self.initial:
                try:
                    fin_id = self.initial['financiamiento']
                    fin = Financiamiento.objects.get(pk=fin_id)
                    
                    # Precargar datos del financiamiento
                    self.fields['nombre_cliente'].initial = fin.nombre_cliente
                    self.fields['oferta'].initial = fin.precio_lote
                    
                    # Precargar datos del lote para mostrar información contextual
                    lote_info = f"Lote: {fin.lote.identificador} - {fin.lote.proyecto.nombre}"
                    self.fields['financiamiento'].help_text = lote_info
                    
                except (ValueError, Financiamiento.DoesNotExist):
                    pass

    def clean(self):
        cleaned_data = super().clean()
        
        # Validar que si se selecciona crédito hipotecario, se especifique la institución
        credito_hipotecario = cleaned_data.get('credito_hipotecario')
        institucion_financiera = cleaned_data.get('institucion_financiera')
        
        if credito_hipotecario == 'Sí' and not institucion_financiera:
            raise forms.ValidationError({
                'institucion_financiera': 'Debe especificar la institución financiera si requiere crédito hipotecario.'
            })
        
        # Validar que la oferta sea positiva
        oferta = cleaned_data.get('oferta')
        if oferta and oferta <= 0:
            raise forms.ValidationError({
                'oferta': 'La oferta debe ser un valor positivo.'
            })
        
        # Si no se especifica destinatario del apartado, usar el nombre del vendedor
        destinatario = cleaned_data.get('destinatario_apartado')
        vendedor = cleaned_data.get('vendedor')
        
        if not destinatario and vendedor:
            cleaned_data['destinatario_apartado'] = vendedor.nombre_completo
        
        return cleaned_data

    def clean_oferta(self):
        oferta = self.cleaned_data.get('oferta')
        financiamiento = self.cleaned_data.get('financiamiento')
        
        # Validar que la oferta no sea mayor al precio del lote (opcional)
        if oferta and financiamiento:
            precio_lote = financiamiento.precio_lote
            if oferta > precio_lote:
                raise forms.ValidationError(
                    f'La oferta (${oferta:.2f}) no puede ser mayor al precio del lote (${precio_lote:.2f}).'
                )
        
        return oferta
