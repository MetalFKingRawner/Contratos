# dashboard/forms.py
from django import forms
from core.models import Propietario, Proyecto, Lote, Cliente, Vendedor, Beneficiario

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
            'fecha_emision_documento': forms.TextInput(attrs={'placeholder': 'Fecha en texto sin abreviaturas (opcional)'}),
            'fecha_emision_contrato': forms.TextInput(attrs={'placeholder': 'Fecha en texto sin abreviaturas (opcional)'}),
            'autoridad': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Autoridad competente (opcional)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer opcionales los campos especificados
        self.fields['autoridad'].required = False
        self.fields['fecha_emision_documento'].required = False
        self.fields['fecha_emision_contrato'].required = False
        
        # Opcional: actualizar las etiquetas para indicar que son opcionales
        self.fields['autoridad'].label = "Autoridad"
        self.fields['fecha_emision_documento'].label = "Fecha Emisión Documento"
        self.fields['fecha_emision_contrato'].label = "Fecha Emisión Contrato"

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
    # CAMPO UNIFICADO para persona que atiende
    persona_atendiendo = forms.ChoiceField(
        choices=[],  # Se llenará dinámicamente
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_persona_atendiendo'
        })
    )
    
    # Mantener los campos originales como hidden para la lógica
    vendedor = forms.ModelChoiceField(
        queryset=Vendedor.objects.all(),
        required=False,
        widget=forms.HiddenInput()
    )
    
    propietario = forms.ModelChoiceField(
        queryset=Propietario.objects.all(),
        required=False,
        widget=forms.HiddenInput()
    )
    
    # Campos para testigos (se crean directamente en el trámite)
    testigo_1_nombre = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Nombre completo del testigo 1'
        })
    )
    
    testigo_2_nombre = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Nombre completo del testigo 2'
        })
    )
    class Meta:
        model = Tramite
        fields = [
            'financiamiento', 
            'cliente', 
            'vendedor',  # Ahora es hidden
            'propietario',  # Ahora es hidden
            'cliente_2',
            'beneficiario_1',
            'beneficiario_2',
            'testigo_1_nombre',  # Estos son campos directos del modelo
            'testigo_2_nombre',  # no necesitan ser ForeignKey
        ]
        widgets = {
            'financiamiento': forms.Select(attrs={
                'class': 'form-select',
                'hx-get': '',  # Puedes añadir funcionalidad HTMX si necesitas
                'hx-target': '#id_cliente'
            }),
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            #'vendedor': forms.Select(attrs={'class': 'form-select'}),
            'cliente_2': forms.Select(attrs={'class': 'form-select'}),
            'beneficiario_1': forms.Select(attrs={'class': 'form-select'}),
            'beneficiario_2': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Construir opciones unificadas para persona_atendiendo
        opciones_persona = []
        
        # Agregar vendedores
        vendedores = Vendedor.objects.all()
        for vendedor in vendedores:
            opciones_persona.append(
                (f'vendedor_{vendedor.id}', f'🧑‍💼 Vendedor: {vendedor.nombre_completo}')
            )
        
        propietarios_filtrados = self.obtener_propietarios_filtrados()
        for propietario in propietarios_filtrados:
            # Diferenciar entre propietarios y apoderados
            emoji = '👑' if propietario.tipo == 'propietario' else '⚖️'
            tipo_texto = 'Propietario' if propietario.tipo == 'propietario' else 'Apoderado'
            opciones_persona.append(
                (f'propietario_{propietario.id}', f'{emoji} {tipo_texto}: {propietario.nombre_completo}')
            )
        
        self.fields['persona_atendiendo'].choices = opciones_persona
        
        # Establecer valor inicial si estamos editando
        if self.instance and self.instance.pk:
            if self.instance.vendedor:
                self.fields['persona_atendiendo'].initial = f'vendedor_{self.instance.vendedor.id}'
                self.fields['vendedor'].initial = self.instance.vendedor
            elif self.instance.propietario:
                self.fields['persona_atendiendo'].initial = f'propietario_{self.instance.propietario.id}'
                self.fields['propietario'].initial = self.instance.propietario

        # Personalizar las querysets si es necesario
        self.fields['financiamiento'].queryset = Financiamiento.objects.all()
        self.fields['cliente'].queryset = Cliente.objects.all()
        #self.fields['vendedor'].queryset = Vendedor.objects.all()
        self.fields['cliente_2'].queryset = Cliente.objects.all()
        self.fields['beneficiario_1'].queryset = Beneficiario.objects.all()
        self.fields['beneficiario_2'].queryset = Beneficiario.objects.all()
        
        # Hacer que el campo cliente_2 no sea requerido
        self.fields['cliente_2'].required = False
        self.fields['beneficiario_1'].required = False
        self.fields['beneficiario_2'].required = False
        self.fields['testigo_1_nombre'].required = False
        self.fields['testigo_2_nombre'].required = False

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
    
    def obtener_propietarios_filtrados(self):
        """
        Filtra propietarios basándose en el proyecto del trámite
        """
        # Si estamos editando un trámite existente
        if self.instance and self.instance.pk:
            if hasattr(self.instance, 'financiamiento') and self.instance.financiamiento:
                return self.filtrar_propietarios_por_financiamiento(self.instance.financiamiento)
        
        # Si es un nuevo trámite o no tiene financiamiento, retornar vacío
        return Propietario.objects.none()

    def filtrar_propietarios_por_financiamiento(self, financiamiento):
        """
        Filtra propietarios relacionados con el proyecto del financiamiento
        """
        try:
            # Obtener el proyecto del lote del financiamiento
            proyecto = financiamiento.lote.proyecto
            # Filtrar propietarios por ese proyecto
            return Propietario.objects.filter(proyecto=proyecto).order_by('tipo', 'nombre_completo')
        except Exception as e:
            print(f"Error filtrando propietarios: {e}")
            # En caso de error, retornar vacío
            return Propietario.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        persona_atendiendo = cleaned_data.get('persona_atendiendo')
        financiamiento = cleaned_data.get('financiamiento')
        
        if persona_atendiendo and financiamiento:
            try:
                tipo, id_str = persona_atendiendo.split('_')
                objeto_id = int(id_str)
                
                if tipo == 'vendedor':
                    try:
                        vendedor = Vendedor.objects.get(id=objeto_id)
                        cleaned_data['vendedor'] = vendedor
                        cleaned_data['propietario'] = None
                    except Vendedor.DoesNotExist:
                        raise forms.ValidationError("El vendedor seleccionado no existe.")
                
                elif tipo == 'propietario':
                    try:
                        propietario = Propietario.objects.get(id=objeto_id)
                        # Validar que el propietario pertenezca al proyecto correcto
                        proyecto_financiamiento = financiamiento.lote.proyecto
                        if propietario.proyecto != proyecto_financiamiento:
                            raise forms.ValidationError(
                                f"El propietario seleccionado no pertenece al proyecto '{proyecto_financiamiento.nombre}'. "
                                f"Pertenece al proyecto '{propietario.proyecto.nombre}'."
                            )
                        cleaned_data['propietario'] = propietario
                        cleaned_data['vendedor'] = None
                    except Propietario.DoesNotExist:
                        raise forms.ValidationError("El propietario seleccionado no existe.")
            except ValueError:
                raise forms.ValidationError("Selección de persona inválida.")
        
        return cleaned_data

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
