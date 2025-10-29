from django import forms
from financiamiento.models import Financiamiento
from core.models import Vendedor, Propietario
from workflow.docs import DOCUMENTOS
from core.models import Cliente

class SolicitudContratoForm(forms.Form):
    # 1) Vinculación al plan de financiamiento (de donde sacaremos nombre_cliente, lote, proyecto…)
    financiamiento = forms.ModelChoiceField(
        queryset=Financiamiento.objects.select_related('lote__proyecto'),
        label="Plan de Financiamiento",
        help_text="Elige el cliente y lote asociados"
    )

    # 2) Fecha de solicitud
    fecha_solicitud = forms.DateField(
        label="Fecha de Solicitud",
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    # 3) Identificación del cliente
    id_tipo    = forms.CharField(label="Documento de Identificación (p.ej. INE, Pasaporte)", max_length=50)
    id_numero  = forms.CharField(label="Número de Identificación", max_length=50)

    # 4) Domicilio y datos del inmueble
    domicilio_cliente = forms.CharField(label="Domicilio del Cliente", widget=forms.Textarea(attrs={'rows': 2}))
    direccion_inmueble = forms.CharField(label="Dirección del Inmueble", widget=forms.TextInput(attrs={'readonly': 'readonly'}))
    superficie         = forms.DecimalField(label="Superficie (m²)", max_digits=10, decimal_places=2, widget=forms.NumberInput(attrs={'readonly': 'readonly'}))
    regimen            = forms.CharField(label="Régimen del Inmueble", widget=forms.TextInput(attrs={'readonly': 'readonly'}))
    valor_venta        = forms.DecimalField(label="Valor de Venta M.N.", max_digits=14, decimal_places=2, widget=forms.NumberInput(attrs={'readonly': 'readonly'}))

    # 5) Valores económicos
    #valor_venta     = forms.DecimalField(label="Valor de Venta M.N.", max_digits=14, decimal_places=2)
    oferta_compra   = forms.DecimalField(label="Oferta de Compra Propuesta M.N.", max_digits=14, decimal_places=2)
    forma_pago      = forms.ChoiceField(
        label="Forma de Pago Propuesta",
        choices=[('contado','Contado'),('financiado','Financiado')],
        widget=forms.RadioSelect
    )
    credito_hipo    = forms.BooleanField(label="Crédito Hipotecario", required=False)
    institucion     = forms.CharField(label="Institución Financiera (si aplica)", max_length=100, required=False)

    # 6) Apartado y depósito
    apartado_monto      = forms.DecimalField(label="Monto de Apartado M.N.", max_digits=14, decimal_places=2)
    apartado_letras = forms.CharField(
        label="Monto en Letras",
        max_length=200,
        required=False,  # Ahora es opcional
        widget=forms.HiddenInput()  # Ocultamos porque lo generaremos automáticamente
    )
    apartado_destino    = forms.CharField(label="A favor de (recibe apartado)", max_length=100)
    # Añadir después de apartado_destino
    apartado_tipo = forms.ChoiceField(
        label="Forma de Pago del Apartado",
        choices=[('efectivo', 'Efectivo'), ('transferencia', 'Transferencia')],
        widget=forms.RadioSelect
    )
    # 7) Vigencia
    vigencia_inicio = forms.DateField(label="Vigencia desde", widget=forms.DateInput(attrs={'type':'date'}))
    vigencia_plazo  = forms.IntegerField(label="Plazo de Vigencia (días naturales)", min_value=1, initial=8)

    # 8) Datos de contacto y firma
    cliente_telefono = forms.CharField(label="Teléfono del Cliente", max_length=20)
    cliente_email    = forms.EmailField(label="Correo Electrónico del Cliente")
    # Vendedor dinámico
    asesor_id = forms.ModelChoiceField(
        queryset=Vendedor.objects.none(),  # Se actualizará con JavaScript
        label="Asesor Inmobiliario"
    )

class AvisoForm(forms.Form):
    firmar = forms.ChoiceField(
        choices=[('sí','Sí, firmaré en pantalla'), ('no','No, lo firmo en oficina')],
        widget=forms.RadioSelect,
        label="¿Deseas firmar digitalmente?",
    )
    aceptar    = forms.BooleanField(label="He leído y acepto el Aviso de Privacidad")
    firma_data = forms.CharField(widget=forms.HiddenInput(), required=False)

class Paso1Form(forms.Form):
    financiamiento = forms.ModelChoiceField(
        queryset=Financiamiento.objects.select_related('lote__proyecto'),
        label="Selecciona tu plan de financiamiento"
    )

class VendorSelectForm(forms.Form):
    persona = forms.ChoiceField(
        choices=[],
        label="Selecciona a la persona que te atendió",
        widget=forms.RadioSelect(attrs={'class': 'd-none'}),
        required=True
    )

    def __init__(self, *args, **kwargs):
        financiamiento = kwargs.pop('financiamiento', None)
        super().__init__(*args, **kwargs)
        
        if financiamiento:
            proyecto_id = financiamiento.lote.proyecto.id
            
            # Obtener vendedores y propietarios
            vendedores = Vendedor.objects.filter(proyectos__id=proyecto_id)
            propietarios = Propietario.objects.all()
            
            # Crear choices para el campo
            choices = []
            
            # Agregar vendedores
            for v in vendedores:
                choices.append((f'vendedor-{v.id}', v.nombre_completo))
            
            # Agregar propietarios
            for p in propietarios:
                choices.append((f'propietario-{p.id}', p.nombre_completo))
            
            self.fields['persona'].choices = choices

class SeleccionDocumentosForm(forms.Form):
    documentos = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple,
        label="Selecciona los documentos que deseas descargar",
    )

    def __init__(self, *args, available_slugs=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar DOCUMENTOS según los slugs disponibles
        if available_slugs is None:
            available_slugs = DOCUMENTOS.keys()
        choices = [
            (slug, DOCUMENTOS[slug]['titulo'])
            for slug in available_slugs
        ]
        self.fields['documentos'].choices = choices

class ClausulasEspecialesForm(forms.Form):
    clausula_pago = forms.CharField(
        label="Cláusula especial de pago (opcional)",
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False
    )
    clausula_deslinde = forms.CharField(
        label="Cláusula adicional después de CUARTA (opcional)",
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False
    )
    clausula_promesa = forms.CharField(
        label="Cláusula adicional después de OCTAVA (opcional)",
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False
    )

class SegundoClienteForm(forms.ModelForm):
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
            'domicilio': forms.Textarea(attrs={'class':'form-control','rows':2}),
        }

class FirmaForm(forms.Form):
    firma_data = forms.CharField(
        widget=forms.HiddenInput(attrs={'id': 'firmaData'}),
        required=True
    )
    aceptar_terminos = forms.BooleanField(
        required=True,
        label="Acepto los términos y condiciones del documento"
    )
