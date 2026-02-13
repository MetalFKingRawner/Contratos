# financiamiento/forms.py

from django import forms
from core.models import Proyecto, Lote, Vendedor, ConfiguracionCommeta
from .models import Financiamiento, CartaIntencion, FinanciamientoCommeta


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
            'precio_lote':        forms.TextInput(attrs={'type': 'text'}),
            'apartado':           forms.TextInput(attrs={'type': 'text'}),
            'monto_pago_completo':forms.TextInput(attrs={'type': 'text'}),
            'enganche':           forms.TextInput(attrs={'type': 'text'}),
            'monto_mensualidad':  forms.TextInput(attrs={'type': 'text'}),
            'fecha_pago_completo': forms.DateInput(attrs={'type': 'date'}),
            'fecha_enganche':      forms.DateInput(attrs={'type': 'date'}),
            'fecha_primer_pago':   forms.DateInput(attrs={'type': 'date'}),
            'fecha_ultimo_pago':   forms.DateInput(attrs={'type': 'date'}),
            'es_cotizacion': forms.CheckboxInput(attrs={'class': 'checkbox-field'}),
            'activo': forms.CheckboxInput(attrs={'class': 'checkbox-field'}),
        }
        help_texts = {
            'es_cotizacion': 'Marcar si es solo una cotización/presupuesto, no un financiamiento real',
            'activo': 'Desmarcar para desactivar este plan',
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance and instance.pk:
            if not kwargs.get('initial'):
                kwargs['initial'] = {}
            
            date_fields = ['fecha_pago_completo', 'fecha_enganche', 'fecha_primer_pago', 'fecha_ultimo_pago']
            for field_name in date_fields:
                field_value = getattr(instance, field_name, None)
                if field_value:
                    kwargs['initial'][field_name] = field_value.strftime('%Y-%m-%d')
            
            money_fields = ['precio_lote', 'apartado', 'monto_pago_completo', 'enganche', 'monto_mensualidad']
            for field_name in money_fields:
                field_value = getattr(instance, field_name, None)
                if field_value is not None:
                    kwargs['initial'][field_name] = str(field_value)
        
        super().__init__(*args, **kwargs)
        
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
        
        opcionales = [
            'fecha_pago_completo', 'monto_pago_completo',
            'enganche', 'fecha_enganche',
            'num_mensualidades', 'monto_mensualidad',
            'fecha_primer_pago', 'fecha_ultimo_pago',
            'es_cotizacion', 'activo'  # Los nuevos campos son opcionales en el formulario
        ]
        for field in opcionales:
            if field in self.fields:
                self.fields[field].required = False

        if not instance:
            self.fields['es_cotizacion'].initial = False
            self.fields['activo'].initial = True

        if self.instance and self.instance.pk:
            if self.instance.tipo_pago == 'contado':
                self.fields['es_cotizacion'].initial = False
        else:
            tipo_pago_initial = self.initial.get('tipo_pago')
            if tipo_pago_initial == 'contado':
                self.fields['es_cotizacion'].initial = False

    def clean(self):
        cd = super().clean()
        tipo = cd.get('tipo_pago')
        es_cotizacion = cd.get('es_cotizacion', False)

        if tipo == 'contado' and es_cotizacion:
            raise forms.ValidationError(
                "Las cotizaciones solo están disponibles para pagos financiados, no para pagos de contado."
            )

        if es_cotizacion:
            if not cd.get('nombre_cliente'):
                raise forms.ValidationError("Para una cotización, el nombre del cliente es obligatorio.")
            if not cd.get('lote'):
                raise forms.ValidationError("Para una cotización, debe seleccionar un lote.")
            if not cd.get('precio_lote'):
                raise forms.ValidationError("Para una cotización, el precio del lote es obligatorio.")
        else:
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

class FinanciamientoCommetaForm(FinanciamientoForm):
    """Formulario especializado para Commeta Community"""
    
    tipo_esquema = forms.ChoiceField(
        label="Tipo de esquema de pagos",
        choices=[
            ('mensualidades_fijas', 'Mensualidades Fijas'),
            ('meses_fuertes', 'Meses Fuertes'),
        ],
        required=True,
        help_text="Selecciona el tipo de estructura de pagos"
    )
    
    monto_mensualidad_normal = forms.DecimalField(
        label="Mensualidad Normal",
        max_digits=12,
        decimal_places=2,
        required=False,
        help_text="Monto en meses normales (solo para esquema de meses fuertes)"
    )
    
    cantidad_meses_fuertes = forms.IntegerField(
        label="Numero de meses fuertes",
        min_value=0,
        required=False,
        help_text="Cantidad total de meses que tendran un pago fuerte"
    )
    
    frecuencia_meses_fuertes = forms.IntegerField(
        label="Frecuencia de meses fuertes",
        min_value=1,
        required=False,
        help_text="Cada cuantos meses se repite un mes fuerte (ej: cada 6 meses)"
    )
    
    monto_mes_fuerte = forms.DecimalField(
        label="Monto del mes fuerte",
        max_digits=12,
        decimal_places=2,
        required=False,
        help_text="Monto a pagar en los meses fuertes"
    )

    class Meta(FinanciamientoForm.Meta):
        widgets = {
            'precio_lote':        forms.TextInput(attrs={'type': 'text'}),
            'apartado':           forms.TextInput(attrs={'type': 'text'}),
            'monto_pago_completo':forms.TextInput(attrs={'type': 'text'}),
            'enganche':           forms.TextInput(attrs={'type': 'text'}),
            'monto_mensualidad':  forms.TextInput(attrs={'type': 'text'}),
            'fecha_pago_completo': forms.DateInput(attrs={'type': 'date'}),
            'fecha_enganche':      forms.DateInput(attrs={'type': 'date'}),
            'fecha_primer_pago':   forms.DateInput(attrs={'type': 'date'}),
            'fecha_ultimo_pago':   forms.DateInput(attrs={'type': 'date'}),
            'es_cotizacion': forms.CheckboxInput(attrs={'class': 'checkbox-field'}),
            'activo': forms.CheckboxInput(attrs={'class': 'checkbox-field'}),
        }

    def __init__(self, *args, **kwargs):
        self.proyecto_commeta = None
        if 'proyecto_commeta' in kwargs:
            self.proyecto_commeta = kwargs.pop('proyecto_commeta')
        
        # ✅ NUEVO: Manejar instancia de FinanciamientoCommeta
        self.instance_commeta = None
        
        # Si la instancia es un FinanciamientoCommeta, guardarla y extraer el Financiamiento
        if 'instance' in kwargs and kwargs['instance'] is not None:
            instance = kwargs['instance']
            
            if isinstance(instance, FinanciamientoCommeta):
                # Guardar la instancia de FinanciamientoCommeta para referencia
                self.instance_commeta = instance
                # Reemplazar con el Financiamiento asociado para el formulario padre
                kwargs['instance'] = instance.financiamiento
                print(f"✅ Convertido FinanciamientoCommeta ID {instance.id} a Financiamiento ID {instance.financiamiento.id}")
        
        super().__init__(*args, **kwargs)
        
        # ✅ CORREGIDO: Ahora self.instance es el Financiamiento (o None)
        # Cargar datos del detalle Commeta si existe
        if self.instance and self.instance.pk:
            # Intentar obtener el detalle Commeta
            detalle_commeta = None
            
            # Primero, usar self.instance_commeta si ya lo tenemos
            if self.instance_commeta:
                detalle_commeta = self.instance_commeta
                print(f"✅ Usando instance_commeta existente: ID {detalle_commeta.id}")
            else:
                # Intentar obtener desde la relación
                try:
                    detalle_commeta = self.instance.detalle_commeta
                    self.instance_commeta = detalle_commeta  # Guardar para referencia
                    print(f"✅ Obtenido detalle_commeta desde relación: ID {detalle_commeta.id}")
                except FinanciamientoCommeta.DoesNotExist:
                    detalle_commeta = None
                    print("⚠️ No hay detalle_commeta para este financiamiento")
            
            # Cargar valores iniciales desde el detalle Commeta
            if detalle_commeta:
                # Campos principales
                self.fields['tipo_esquema'].initial = detalle_commeta.tipo_esquema
                
                # Campos de meses fuertes
                self.fields['monto_mensualidad_normal'].initial = detalle_commeta.monto_mensualidad_normal
                self.fields['cantidad_meses_fuertes'].initial = detalle_commeta.cantidad_meses_fuertes
                self.fields['frecuencia_meses_fuertes'].initial = detalle_commeta.frecuencia_meses_fuertes
                self.fields['monto_mes_fuerte'].initial = detalle_commeta.monto_mes_fuerte
                
                # También cargar monto_pago_final del financiamiento base
                if hasattr(detalle_commeta.financiamiento, 'monto_pago_final'):
                    self.fields['monto_pago_final'].initial = detalle_commeta.financiamiento.monto_pago_final
                
                print(f"✅ Valores iniciales cargados desde detalle_commeta ID {detalle_commeta.id}")
                print(f"   - Tipo esquema: {detalle_commeta.tipo_esquema}")
                print(f"   - Monto mensualidad normal: {detalle_commeta.monto_mensualidad_normal}")
                print(f"   - Cantidad meses fuertes: {detalle_commeta.cantidad_meses_fuertes}")
        
        # ✅ CORREGIDO: Manejar proyecto_commeta y lotes
        if self.proyecto_commeta: 
            self.fields['lote'].queryset = self.proyecto_commeta.lotes.filter(activo=True)
            
            # Solo establecer lote inicial si no hay uno ya establecido
            if not self.initial.get('lote') and self.fields['lote'].queryset.exists():
                self.initial['lote'] = self.fields['lote'].queryset.first()
                print(f"✅ Lote inicial establecido: {self.initial['lote']}")
        
        # ✅ CORREGIDO: Para edición, ajustar el queryset de lotes
        elif self.instance and self.instance.pk and hasattr(self.instance, 'lote'):
            if self.instance.lote.es_commeta:
                proyecto = self.instance.lote.proyecto
                # Mostrar todos los lotes activos de este proyecto Commeta
                self.fields['lote'].queryset = proyecto.lotes.filter(activo=True)
                print(f"✅ Queryset ajustado para proyecto Commeta: {proyecto.nombre}")

        # ✅ CORREGIDO: Ocultar campo proyecto si es Commeta
        if self.instance and self.instance.pk and self.instance.lote.es_commeta:
            self.fields['proyecto'].widget = forms.HiddenInput()
            self.fields['proyecto'].required = False
            print("✅ Campo proyecto oculto para Commeta")

    def clean(self):
        cleaned_data = super().clean()
        
        lote = cleaned_data.get('lote')
        tipo_pago = cleaned_data.get('tipo_pago')
        tipo_esquema = cleaned_data.get('tipo_esquema')
        
        if lote and lote.es_commeta and tipo_pago == 'financiado':
            if tipo_esquema == 'meses_fuertes':
                cantidad_meses_fuertes = cleaned_data.get('cantidad_meses_fuertes')
                monto_mes_fuerte = cleaned_data.get('monto_mes_fuerte')
                monto_mensualidad_normal = cleaned_data.get('monto_mensualidad_normal')
                num_mensualidades = cleaned_data.get('num_mensualidades')
                
                if not cantidad_meses_fuertes:
                    raise forms.ValidationError(
                        "Para esquema de meses fuertes, debe especificar la cantidad de meses fuertes."
                    )
                
                if not monto_mes_fuerte:
                    raise forms.ValidationError(
                        "Para esquema de meses fuertes, debe especificar el monto del mes fuerte."
                    )
                
                if not monto_mensualidad_normal:
                    raise forms.ValidationError(
                        "Para esquema de meses fuertes, debe especificar el monto de mensualidad normal."
                    )
                
                if num_mensualidades and cantidad_meses_fuertes > num_mensualidades:
                    raise forms.ValidationError(
                        f"Los meses fuertes ({cantidad_meses_fuertes}) no pueden exceder "
                        f"el total de mensualidades ({num_mensualidades})."
                    )
            
            elif tipo_esquema == 'mensualidades_fijas':
                monto_mensualidad = cleaned_data.get('monto_mensualidad')
                if not monto_mensualidad:
                    raise forms.ValidationError(
                        "Para esquema de mensualidades fijas, debe especificar el monto de la mensualidad."
                    )

        return cleaned_data

    def save(self, commit=True):
        # Guardar el Financiamiento base
        financiamiento = super().save(commit=commit)
        
        if financiamiento.lote.es_commeta and commit and financiamiento.tipo_pago == 'financiado':
            from .utils import obtener_configuracion_commeta, calcular_meses_fuertes_inicio
            
            configuracion = obtener_configuracion_commeta(financiamiento.lote)
            if not configuracion:
                raise ValueError("El lote Commeta no tiene configuracion asignada")
            
            tipo_esquema = self.cleaned_data.get('tipo_esquema')
            cantidad_meses_fuertes = self.cleaned_data.get('cantidad_meses_fuertes')
            frecuencia_meses_fuertes = self.cleaned_data.get('frecuencia_meses_fuertes')
            
            meses_fuertes_calculados = []
            if tipo_esquema == 'meses_fuertes' and cantidad_meses_fuertes and financiamiento.num_mensualidades:
                meses_fuertes_calculados = calcular_meses_fuertes_inicio(
                    total_meses=financiamiento.num_mensualidades,
                    cantidad_meses_fuertes=cantidad_meses_fuertes,
                    frecuencia=frecuencia_meses_fuertes
                )

            # ✅ CORREGIDO: Usar self.instance_commeta si existe (edición)
            if hasattr(self, 'instance_commeta') and self.instance_commeta:
                detalle_commeta = self.instance_commeta
                print(f"✅ Editando FinanciamientoCommeta existente ID {detalle_commeta.id}")
            else:
                # Crear nuevo FinanciamientoCommeta
                try:
                    detalle_commeta = financiamiento.detalle_commeta
                    print(f"✅ Usando detalle_commeta existente ID {detalle_commeta.id}")
                except FinanciamientoCommeta.DoesNotExist:
                    detalle_commeta = FinanciamientoCommeta(financiamiento=financiamiento)
                    print("✅ Creando nuevo FinanciamientoCommeta")
            
            # Actualizar campos
            detalle_commeta.tipo_esquema = tipo_esquema
            detalle_commeta.cantidad_meses_fuertes = cantidad_meses_fuertes
            detalle_commeta.frecuencia_meses_fuertes = frecuencia_meses_fuertes
            detalle_commeta.monto_mes_fuerte = self.cleaned_data.get('monto_mes_fuerte')
            detalle_commeta.monto_mensualidad_normal = self.cleaned_data.get('monto_mensualidad_normal')
            detalle_commeta.meses_fuertes_calculados = meses_fuertes_calculados
            detalle_commeta.configuracion_original = configuracion
            
            detalle_commeta.save()
            print(f"✅ FinanciamientoCommeta guardado: ID {detalle_commeta.id}")
        
        return financiamiento

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


