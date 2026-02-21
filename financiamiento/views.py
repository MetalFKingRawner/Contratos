from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import Financiamiento, CartaIntencion, FinanciamientoCommeta
from .forms import FinanciamientoForm, CartaIntencionForm, FinanciamientoCommetaForm
from core.models import Lote, ConfiguracionCommeta, Proyecto  # Importamos el modelo Lote
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
import json

from datetime import date
from workflow.builders import fmt_money
import os, base64, tempfile
from docxtpl import DocxTemplate,InlineImage

# En financiamiento/views.py - ACTUALIZAR la vista ajax_configuracion_commeta
@require_POST
def ajax_validar_estructura_commeta(request):
    """Vista AJAX para validar estructura de pagos antes de guardar"""
    try:
        data = json.loads(request.body)
        
        financiamiento_data = data.get('financiamiento', {})
        detalle_commeta_data = data.get('detalle_commeta', {})
        
        from .utils import validar_estructura_completa_commeta
        
        es_valido, mensaje, desglose = validar_estructura_completa_commeta(
            financiamiento_data,
            detalle_commeta_data
        )
        
        return JsonResponse({
            'valido': es_valido,
            'mensaje': mensaje,
            'desglose': desglose
        })
        
    except Exception as e:
        return JsonResponse({
            'valido': False,
            'mensaje': f'Error al validar: {str(e)}',
            'desglose': {}
        }, status=400)

@require_GET
def ajax_configuracion_commeta(request, lote_id):
    """Vista AJAX para obtener configuración Commeta de un lote"""
    try:
        configuracion = ConfiguracionCommeta.objects.get(lote_id=lote_id)
        data = {
            'configuracion': {
                'zona': configuracion.zona,
                'zona_display': configuracion.get_zona_display(),
                'precio_base': str(configuracion.precio_base),
                'apartado_sugerido': str(configuracion.apartado_sugerido),
                'enganche_sugerido': str(configuracion.enganche_sugerido),
                'mensualidad_sugerida': str(configuracion.mensualidad_sugerida) if configuracion.mensualidad_sugerida else None,
                'monto_mensualidad_normal': str(configuracion.monto_mensualidad_normal) if configuracion.monto_mensualidad_normal else None,
                'monto_mes_fuerte': str(configuracion.monto_mes_fuerte) if configuracion.monto_mes_fuerte else None,
                'monto_pago_final': str(configuracion.monto_pago_final) if configuracion.monto_pago_final else None,
                'frecuencia_meses_fuertes': configuracion.frecuencia_meses_fuertes,
                'total_meses': configuracion.total_meses,
                'cantidad_meses_fuertes_sugerida': configuracion.cantidad_meses_fuertes_sugerida,
                'tipo_esquema': configuracion.tipo_esquema,  # ✅ NUEVO
            }
        }
        return JsonResponse(data)
    except ConfiguracionCommeta.DoesNotExist:
        return JsonResponse({'configuracion': None})

class FinanciamientoListView(ListView):
    model = Financiamiento
    template_name = "financiamiento/list.html"
    context_object_name = "planes"
    
    def get_queryset(self):
        # Opcional: puedes filtrar o ordenar los planes aquí
        return Financiamiento.objects.select_related(
            'lote__proyecto',  # Para acceder a lote.proyecto sin consulta adicional
            'detalle_commeta'  # Para acceder a detalle_commeta sin consulta adicional
        ).all().order_by('-creado_en')


class FinanciamientoCreateView(CreateView):
    model = Financiamiento
    form_class = FinanciamientoForm
    template_name = "financiamiento/form_dinamico.html"
    success_url = reverse_lazy('financiamiento:list')

    def get_form_class(self):
        """Determinar el formulario basado en parámetros GET o proyecto seleccionado"""
        # Si viene con parámetro de proyecto Commeta
        proyecto_commeta_id = self.request.GET.get('proyecto_commeta')
        if proyecto_commeta_id:
            try:
                proyecto = Proyecto.objects.get(id=proyecto_commeta_id, tipo_proyecto='commeta')
                return FinanciamientoCommetaForm
            except Proyecto.DoesNotExist:
                pass
        
        # Lógica existente para detección en tiempo real
        proyecto_id = None
        if self.request.method == 'POST':
            proyecto_id = self.request.POST.get('proyecto')
        elif self.request.method == 'GET':
            proyecto_id = self.request.GET.get('proyecto')
            
        if proyecto_id:
            try:
                proyecto = Proyecto.objects.get(id=proyecto_id)
                if proyecto.tipo_proyecto == 'commeta':
                    return FinanciamientoCommetaForm
            except Proyecto.DoesNotExist:
                pass
        
        return FinanciamientoForm
    
    def get_initial(self):
        """Pre-configurar datos iniciales para Commeta"""
        initial = super().get_initial()
        
        # Si es un proyecto Commeta via GET parameter
        proyecto_commeta_id = self.request.GET.get('proyecto_commeta')
        if proyecto_commeta_id:
            try:
                proyecto = Proyecto.objects.get(id=proyecto_commeta_id, tipo_proyecto='commeta')
                initial['proyecto'] = proyecto
                
                # También podemos pre-seleccionar el primer lote disponible
                lotes_disponibles = proyecto.lotes.filter(activo=True)
                if lotes_disponibles.exists():
                    initial['lote'] = lotes_disponibles.first()
            except Proyecto.DoesNotExist:
                pass
        
        return initial

    def get_template_names(self):
        """
        Determinar qué template usar basado en el tipo de proyecto
        """
        # CASO 1: Si es un proyecto Commeta pre-cargado via URL parameter
        if self.request.GET.get('proyecto_commeta'):
            return ["financiamiento/form_commeta_precargado.html"]
        
        # CASO 2: Si estamos editando un financiamiento Commeta existente
        if self.object and self.object.pk and self.object.lote.es_commeta:
            return ["financiamiento/form_commeta_precargado.html"]
        
        # CASO 3: Para nuevos financiamientos con detección en tiempo real
        form_class = self.get_form_class()
        if form_class == FinanciamientoCommetaForm:
            return ["financiamiento/form_commeta_precargado.html"]
        
        # CASO POR DEFECTO: Proyectos normales
        return ["financiamiento/form_dinamico.html"]

    def get_context_data(self, **kwargs):
        """Agregar información específica de Commeta al contexto"""
        context = super().get_context_data(**kwargs)
        
        proyectos_commeta = Proyecto.objects.filter(tipo_proyecto='commeta').values_list('id', flat=True)
        context['proyectos_commeta_ids'] = list(proyectos_commeta)
        
        # Información para pre-cargar Commeta
        proyecto_commeta_id = self.request.GET.get('proyecto_commeta')
        if proyecto_commeta_id:
            try:
                proyecto_commeta = Proyecto.objects.get(id=proyecto_commeta_id)
                context['proyecto_commeta_precargado'] = proyecto_commeta
                
                # ✅ CORRECCIÓN: Obtener los lotes activos de ESTE proyecto Commeta
                context['lotes_commeta'] = proyecto_commeta.lotes.filter(activo=True)
                print(f"✅ Lotes Commeta cargados: {context['lotes_commeta'].count()} lotes")

                # ✅ NUEVO: Indicar que estamos en modo creación
                context['es_edicion'] = False
                
            except Proyecto.DoesNotExist:
                print("❌ Proyecto Commeta no encontrado")
        
        return context

    def form_valid(self, form):
        # CORRECCIÓN: form.cleaned_data.get('proyecto') devuelve un OBJETO Proyecto, no un ID
        proyecto = form.cleaned_data.get('proyecto')  # ← Esto ya es un objeto Proyecto
        
        if proyecto and proyecto.tipo_proyecto == 'commeta':
            # Usar el formulario Commeta para validación y guardado
            form = FinanciamientoCommetaForm(self.request.POST, instance=form.instance)
            if form.is_valid():
                return self.form_valid_commeta(form)
        
        # Para proyectos normales
        return super().form_valid(form)

    def form_valid_commeta(self, form):
        """
        Manejar el guardado específico para Commeta
        """
        response = super().form_valid(form)
        
        # Lógica específica de Commeta (marcar lote como inactivo, etc.)
        lote = form.cleaned_data['lote']
        es_cotizacion = form.cleaned_data.get('es_cotizacion', False)
        
        if not es_cotizacion:
            lote.activo = False
            lote.save()
            messages.success(self.request, f"Financiamiento Commeta creado exitosamente. El lote {lote.identificador} ha sido marcado como inactivo.")
        else:
            messages.success(self.request, f"Cotización Commeta creada exitosamente. El lote {lote.identificador} permanece disponible.")
        
        return response
    
    def get_form_kwargs(self):
        """Pasar el proyecto_commeta al formulario si existe"""
        kwargs = super().get_form_kwargs()
        
        # ✅ CORRECCIÓN: Pasar el proyecto Commeta al formulario
        proyecto_commeta_id = self.request.GET.get('proyecto_commeta')
        if proyecto_commeta_id:
            try:
                proyecto_commeta = Proyecto.objects.get(id=proyecto_commeta_id)
                kwargs['proyecto_commeta'] = proyecto_commeta
            except Proyecto.DoesNotExist:
                pass
        
        return kwargs


class FinanciamientoUpdateView(UpdateView):
    model = Financiamiento
    form_class = FinanciamientoForm
    template_name = "financiamiento/form.html"
    success_url = reverse_lazy('financiamiento:list')

    def get_form_class(self):
        """
        Detecta automáticamente si el financiamiento es Commeta
        y retorna el formulario correspondiente
        """
        if self.object.lote.es_commeta:
            return FinanciamientoCommetaForm
        return FinanciamientoForm

    def get_template_names(self):
        """
        Retorna template específico para Commeta si aplica
        """
        if self.object.lote.es_commeta:
            return ["financiamiento/form_commeta_precargado.html"]
        return ["financiamiento/form.html"]

    def get_context_data(self, **kwargs):
        """
        Agregar información específica para Commeta al contexto
        """
        context = super().get_context_data(**kwargs)
        
        # Si es un financiamiento Commeta, agregar el proyecto y lotes al contexto
        if self.object.lote.es_commeta:
            proyecto_commeta = self.object.lote.proyecto
            context['proyecto_commeta_precargado'] = proyecto_commeta
            context['lotes_commeta'] = proyecto_commeta.lotes.filter(activo=True)

            # ✅ NUEVO: Indicar que estamos en modo edición
            context['es_edicion'] = True
            
            # Debug
            print(f"✅ UpdateView - Proyecto Commeta: {proyecto_commeta.nombre}")
            print(f"✅ UpdateView - Lotes disponibles: {context['lotes_commeta'].count()}")
            print(f"✅ UpdateView - Modo: EDICIÓN (no se cargará configuración automáticamente)")
        
        return context

    def get_form_kwargs(self):
        """
        Pasar el proyecto_commeta al formulario si es Commeta
        """
        kwargs = super().get_form_kwargs()
        
        if self.object.lote.es_commeta:
            kwargs['proyecto_commeta'] = self.object.lote.proyecto
        
        return kwargs

    def get_initial(self):
        """
        Pre-configurar datos iniciales para edición
        """
        initial = super().get_initial()
        
        # Si es Commeta, asegurarnos de que el proyecto esté en initial
        if self.object.lote.es_commeta:
            initial['proyecto'] = self.object.lote.proyecto
        
        return initial

    def form_valid(self, form):
        # Para Commeta, usar el formulario específico
        if self.object.lote.es_commeta and isinstance(form, FinanciamientoForm):
            # Recrear el formulario como FinanciamientoCommetaForm
            form = FinanciamientoCommetaForm(
                self.request.POST, 
                instance=form.instance,
                proyecto_commeta=self.object.lote.proyecto
            )
            
            if not form.is_valid():
                print("❌ ERRORES en formulario Commeta:")
                for field, errors in form.errors.items():
                    print(f"   {field}: {errors}")
                return self.form_invalid(form)
        
        # Obtenemos la instancia actual antes de guardar
        instance_anterior = self.get_object()
        es_cotizacion_anterior = instance_anterior.es_cotizacion
        lote_anterior = instance_anterior.lote
        
        # Guardamos los cambios
        response = super().form_valid(form)
        
        # Obtenemos los nuevos valores después de guardar
        es_cotizacion_nueva = form.instance.es_cotizacion
        lote_nuevo = form.instance.lote
        
        # Lógica para manejar cambios en el estado de cotización o lote
        self._manejar_cambios_estado(
            es_cotizacion_anterior, 
            es_cotizacion_nueva, 
            lote_anterior, 
            lote_nuevo
        )
        
        messages.success(self.request, f"{'Cotización' if es_cotizacion_nueva else 'Financiamiento'} actualizado exitosamente.")
        
        return response

    def _manejar_cambios_estado(self, es_cotizacion_anterior, es_cotizacion_nueva, lote_anterior, lote_nuevo):
        """
        Maneja los cambios entre cotización/financiamiento y cambios de lote
        """
        # CASO 1: Cambió de cotización a financiamiento real
        if es_cotizacion_anterior and not es_cotizacion_nueva:
            # Ahora es un financiamiento real, marcar el lote como inactivo
            lote_nuevo.activo = False
            lote_nuevo.save()
            # Si el lote anterior era diferente, reactivarlo
            if lote_anterior != lote_nuevo and lote_anterior:
                lote_anterior.activo = True
                lote_anterior.save()
        
        # CASO 2: Cambió de financiamiento real a cotización
        elif not es_cotizacion_anterior and es_cotizacion_nueva:
            # Ahora es solo cotización, reactivar el lote anterior
            if lote_anterior:
                lote_anterior.activo = True
                lote_anterior.save()
            # Si el lote nuevo es diferente, también reactivarlo (por si acaso)
            if lote_nuevo != lote_anterior:
                lote_nuevo.activo = True
                lote_nuevo.save()
        
        # CASO 3: Sigue siendo financiamiento real pero cambió de lote
        elif not es_cotizacion_anterior and not es_cotizacion_nueva and lote_anterior != lote_nuevo:
            # Desactivar el nuevo lote
            lote_nuevo.activo = False
            lote_nuevo.save()
            # Reactivar el lote anterior
            if lote_anterior:
                lote_anterior.activo = True
                lote_anterior.save()
        
        # CASO 4: Sigue siendo cotización pero cambió de lote
        elif es_cotizacion_anterior and es_cotizacion_nueva and lote_anterior != lote_nuevo:
            # Ambos lotes deben estar activos (solo son cotizaciones)
            if lote_anterior:
                lote_anterior.activo = True
                lote_anterior.save()
            lote_nuevo.activo = True
            lote_nuevo.save()

    def form_invalid(self, form):
        messages.error(self.request, "Por favor corrige los errores en el formulario.")
        return super().form_invalid(form)
    
class CartaIntencionListView(ListView):
    model = CartaIntencion
    template_name = "financiamiento/carta_intencion_list.html"
    context_object_name = "cartas"
    
    def get_queryset(self):
        # Ordenar por fecha de creación (más recientes primero)
        return CartaIntencion.objects.all().order_by('-creado_en')


class CartaIntencionCreateView(CreateView):
    model = CartaIntencion
    form_class = CartaIntencionForm
    template_name = "financiamiento/carta_intencion_form.html"
    success_url = reverse_lazy('financiamiento:carta_intencion_list')

    def get_initial(self):
        """Precargar datos iniciales basados en parámetros de URL"""
        initial = super().get_initial()
        
        # Si se pasa un financiamiento específico por URL
        financiamiento_id = self.request.GET.get('financiamiento_id')
        if financiamiento_id:
            try:
                financiamiento = Financiamiento.objects.get(pk=financiamiento_id)
                initial['financiamiento'] = financiamiento
                
                # Precargar datos del financiamiento
                initial['nombre_cliente'] = financiamiento.nombre_cliente
                initial['oferta'] = financiamiento.precio_lote
                
            except Financiamiento.DoesNotExist:
                pass
        
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request, 
            f"Carta de intención creada exitosamente para {form.instance.nombre_cliente}."
        )
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Por favor corrige los errores en el formulario.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Agregar información adicional si se está creando desde un financiamiento específico
        financiamiento_id = self.request.GET.get('financiamiento_id')
        if financiamiento_id:
            try:
                financiamiento = Financiamiento.objects.get(pk=financiamiento_id)
                context['financiamiento_info'] = {
                    'lote': financiamiento.lote.identificador,
                    'proyecto': financiamiento.lote.proyecto.nombre,
                    'precio_lote': financiamiento.precio_lote,
                    'apartado': financiamiento.apartado,
                }
            except Financiamiento.DoesNotExist:
                pass
        
        return context


class CartaIntencionUpdateView(UpdateView):
    model = CartaIntencion
    form_class = CartaIntencionForm
    template_name = "financiamiento/carta_intencion_form.html"
    success_url = reverse_lazy('financiamiento:carta_intencion_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request, 
            f"Carta de intención actualizada exitosamente para {form.instance.nombre_cliente}."
        )
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Por favor corrige los errores en el formulario.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Agregar información del financiamiento relacionado para referencia
        if self.object and self.object.financiamiento:
            fin = self.object.financiamiento
            context['financiamiento_info'] = {
                'lote': fin.lote.identificador,
                'proyecto': fin.lote.proyecto.nombre,
                'precio_lote': fin.precio_lote,
                'apartado': fin.apartado,
                'tipo_pago': fin.tipo_pago,
            }
        
        return context
    
@require_GET
def financiamiento_ajax_data(request, pk):
    """Vista AJAX para obtener datos de un financiamiento específico"""
    try:
        fin = Financiamiento.objects.get(pk=pk)
        data = {
            'direccion': fin.lote.proyecto.ubicacion,
            'numero_lote': fin.lote.identificador,
            'regimen': fin.lote.proyecto.tipo_contrato,
            'precio_lote': str(fin.precio_lote),
            'apartado': str(fin.apartado),
            'nombre_cliente': fin.nombre_cliente,  # Asegurarnos de incluir el nombre del cliente
        }
        return JsonResponse(data)
    except Financiamiento.DoesNotExist:
        return JsonResponse({'error': 'Financiamiento no encontrado'}, status=404)

import os
from docxtpl import DocxTemplate
from docx.shared import Mm
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
from workflow.utils import numero_a_letras, calcular_superficie
from pdfs.utils import convert_docx_to_pdf

def build_carta_intencion_from_instance(carta, request=None, tpl=None):
    """
    Builder específico para carta de intención desde la instancia de CartaIntencion
    """
    from datetime import date
    
    fecha = date.today()
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    fin = carta.financiamiento
    lote = fin.lote
    superficie = fin.lote.superficie_m2
    
    # Determinar forma de pago para el documento
    forma_pago_doc = 'Contado' if fin.tipo_pago == 'contado' else 'Financiado'
    
    context = {
        'LUGAR': 'Oaxaca de Juárez, Oax',
        # Fecha de emisión
        'DIA_1': fecha.day,
        'MES_1': meses[fecha.month - 1].upper(),
        'ANIO_1': str(fecha.year)[-2:],
        
        # Datos del cliente (desde la carta de intención)
        'NOMBRE_CLIENTE': carta.nombre_cliente,
        'DIRECCION_CLIENTE': carta.domicilio,
        'TIPO_ID': carta.tipo_id,
        'NUMERO_ID': carta.numero_id,
        'TELEFONO_CLIENTE': carta.telefono_cliente,
        'EMAIL_CLIENTE': carta.correo_cliente,
        
        # Datos del lote (desde el financiamiento)
        'DIRECCION_INMUEBLE': fin.lote.proyecto.ubicacion,
        'NUMERO_LOTE': fin.lote.identificador,
        'SUPERFICIE': superficie,
        'REGIMEN': fin.lote.proyecto.tipo_contrato,
        
        # Datos del vendedor (desde la carta de intención)
        'NOMBRE_ASESOR': carta.vendedor.nombre_completo,
        'TELEFONO_ASESOR': carta.vendedor.telefono,
        
        # Datos de pago/apartado
        'VALOR_VENTA': f"{fin.precio_lote:.2f}",
        'OFERTA_COMPRA': f"{carta.oferta:.2f}",
        'FORMA_PAGO': forma_pago_doc,
        'CREDITO_HIPOTECARIO': carta.credito_hipotecario,
        'INSTITUCION_FINANCIERA': carta.institucion_financiera or '',
        'MONTO_APARTADO': f"{fin.apartado:.2f}",
        'MONTO_LETRAS': numero_a_letras(float(fin.apartado)),
        'DESTINATARIO_APARTADO': carta.destinatario_apartado or carta.vendedor.nombre_completo,
        'TIPO_PAGO': carta.forma_pago.lower(),
        
        # Vigencia (usamos fecha actual + 30 días por defecto)
        'VIGENCIA_DIA': fin.creado_en.day,
        'VIGENCIA_MES': meses[fin.creado_en.month - 1],
        'VIGENCIA_ANIO': str(fin.creado_en.year)[-2:],
    }
    
    # Firma del cliente (por ahora vacía, puedes agregarla después si es necesario)
    context['FIRMA_CLIENTE'] = ''
    
    return context

def descargar_carta_intencion_pdf(request, pk):
    """
    Vista para descargar una carta de intención en PDF
    """
    # Obtener la carta de intención
    carta = get_object_or_404(CartaIntencion, pk=pk)
    
    # Ruta a la plantilla de carta de intención
    tpl_path = os.path.join(settings.BASE_DIR, 'pdfs/templates/pdfs/carta_intencion_template.docx')
    
    # Verificar que la plantilla existe
    if not os.path.exists(tpl_path):
        return HttpResponse("Plantilla no encontrada", status=500)
    
    try:
        # Cargar plantilla
        tpl = DocxTemplate(tpl_path)
        
        # Generar contexto
        context = build_carta_intencion_from_instance(carta, request=request, tpl=tpl)
        
        # Renderizar plantilla
        tpl.render(context)
        
        # Crear directorio temporal si no existe
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Guardar DOCX temporal
        tmp_docx = os.path.join(temp_dir, f"carta_intencion_{carta.id}.docx")
        tpl.save(tmp_docx)
        
        # Convertir a PDF
        pdf_filename = f"carta_intencion_{carta.nombre_cliente.replace(' ', '_')}_{carta.id}.pdf"
        tmp_pdf = os.path.join(temp_dir, pdf_filename)
        
        success = convert_docx_to_pdf(tmp_docx, tmp_pdf)
        
        if success and os.path.exists(tmp_pdf):
            # Leer el PDF y enviarlo como respuesta
            with open(tmp_pdf, 'rb') as pdf_file:
                response = HttpResponse(pdf_file.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
                
                # Limpiar archivos temporales después de enviar
                try:
                    os.remove(tmp_docx)
                    os.remove(tmp_pdf)
                except:
                    pass  # Ignorar errores de limpieza
                
                return response
        else:
            # Si falla la conversión a PDF, enviar el DOCX
            with open(tmp_docx, 'rb') as docx_file:
                response = HttpResponse(
                    docx_file.read(), 
                    content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                )
                response['Content-Disposition'] = f'attachment; filename="carta_intencion_{carta.id}.docx"'
                
                # Limpiar archivo temporal
                try:
                    os.remove(tmp_docx)
                except:
                    pass
                
                return response
    
    except Exception as e:
        # En caso de error, retornar mensaje
        return HttpResponse(f"Error al generar el documento: {str(e)}", status=500)


def build_financiamiento_cotiza_context(fin, request=None):
    """
    Context para Tabla de Financiamiento
    """
    # 1) Fecha actual
    hoy = date.today()
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    # 2) Cálculos iniciales
    resta_apartado = float(fin.precio_lote) - float(fin.apartado)
    resta_enganche = resta_apartado - float(fin.enganche or 0)
    
    # 3) Generar lista de pagos para las mensualidades
    pagos = []
    saldo_actual = resta_enganche
    
    if fin.tipo_pago == 'financiado' and fin.num_mensualidades and fin.monto_mensualidad:
        fecha_pago = fin.fecha_primer_pago
        
        for i in range(1, fin.num_mensualidades + 1):
            # Determinar monto de la cuota - CORREGIDO
            if i == fin.num_mensualidades and fin.monto_pago_final:
                # Si hay monto final específico
                cuota = float(fin.monto_pago_final)
            elif i == fin.num_mensualidades and not fin.monto_pago_final:
                # En el último pago, la cuota es el saldo actual
                cuota = saldo_actual
            else:
                cuota = float(fin.monto_mensualidad)
            
            # Calcular saldo final
            saldo_final = max(0, saldo_actual - cuota)
            
            pagos.append({
                'numero': i,
                'fecha': fecha_pago.strftime("%d/%m/%Y") if fecha_pago else '',
                'saldo_inicial': fmt_money(saldo_actual),  # Formateado con comas
                'cuota': fmt_money(cuota),  # Formateado con comas
                'saldo_final': fmt_money(saldo_final),  # Formateado con comas
            })
            
            # Actualizar para siguiente pago
            saldo_actual = saldo_final
            if fecha_pago:
                # Avanzar un mes (manejo simple de fecha)
                try:
                    if fecha_pago.month == 12:
                        fecha_pago = fecha_pago.replace(year=fecha_pago.year + 1, month=1)
                    else:
                        fecha_pago = fecha_pago.replace(month=fecha_pago.month + 1)
                except:
                    # En caso de error, dejamos la misma fecha
                    pass

    # 4) Obtener nombre del vendedor/usuario actual
    nombre_vendedor = "Administración"  # Valor por defecto

    if request and request.user.is_authenticated:
        # Intentar obtener el nombre completo del usuario
        nombre_completo = None
        
        # Si el usuario tiene first_name y last_name
        if request.user.first_name and request.user.last_name:
            nombre_completo = f"{request.user.first_name} {request.user.last_name}"
        # Si solo tiene first_name
        elif request.user.first_name:
            nombre_completo = request.user.first_name
        # Si no, usar el username
        else:
            nombre_completo = request.user.username
        
        nombre_vendedor = nombre_completo.upper()

    fecha_inicio = fin.fecha_primer_pago
    fecha_final = fin.fecha_ultimo_pago
    superfici = fin.lote.superficie_m2

    # 5) Construir contexto
    context = {
        # Fechas
        'FECHA_FINANCIAMIENTO': f"{hoy.day} de {meses[hoy.month-1]} de {hoy.year}",
        'FECHA_APARTADO': fin.creado_en.strftime("%d/%m/%Y") if fin.creado_en else hoy.strftime("%d/%m/%Y"),
        'FECHA_ENGANCHE': fin.fecha_enganche.strftime("%d/%m/%Y") if fin.fecha_enganche else '',
        
        # Datos del lote y cliente
        'NOMBRE_CLIENTE': fin.nombre_cliente.upper(),
        'NOMBRE_VENDEDOR': nombre_vendedor,
        'NOMBRE_PROYECTO': fin.lote.proyecto.nombre.upper(),
        #'UBICACION_LOTE': fin.lote.proyecto.ubicacion,
        'IDENTIFICADOR_LOTE': fin.lote.identificador,
        #'REGIMEN': fin.lote.proyecto.tipo_contrato,
        'METROS_CUADRADOS': superfici,
        'PRECIO_METRO':fmt_money((float(fin.precio_lote)/float(superfici))),
        # Montos financiamiento - FORMATEADOS CON COMAS
        'PRECIO_LOTE': fmt_money(fin.precio_lote),
        'APARTADO': fmt_money(fin.apartado),
        'ENGANCHE': fmt_money(fin.enganche) if fin.enganche else '',
        'TOTAL_FIN': fmt_money(resta_enganche),
        'NUM_MESES': fin.num_mensualidades,
        'MENSUALIDAD_FIJA': fmt_money(fin.monto_mensualidad),
        'MENSUALIDAD_FINAL': fmt_money(fin.monto_pago_final),
        'FECHA_INICIO': f"{fecha_inicio.day} de {meses[fecha_inicio.month-1]} de {fecha_inicio.year}",
        'FECHA_FINAL': f"{fecha_final.day} de {meses[fecha_final.month-1]} de {fecha_final.year}",

        # Cálculos intermedios - FORMATEADOS CON COMAS
        'RESTA_APARTADO': fmt_money(resta_apartado),
        'RESTA_ENGANCHE': fmt_money(resta_enganche),
        
        # Lista de pagos
        'pagos': pagos,
    }

    return context

def descargar_financiamiento_cotiza_pdf(request, pk):
    """
    Vista para descargar un financiamiento (cotización) en PDF
    """
    # Obtener el financiamiento
    from .models import Financiamiento
    fin = get_object_or_404(Financiamiento, pk=pk)
    
    # Ruta a la plantilla de financiamiento cotización
    tpl_path = os.path.join(settings.BASE_DIR, 'pdfs/templates/pdfs/cotiza_financia_n.docx')
    
    # Verificar que la plantilla existe
    if not os.path.exists(tpl_path):
        return HttpResponse("Plantilla no encontrada", status=500)
    
    try:
        # Cargar plantilla
        tpl = DocxTemplate(tpl_path)
        
        # Generar contexto - pasamos request para obtener el usuario actual
        context = build_financiamiento_cotiza_context(fin, request=request)
        
        # Renderizar plantilla
        tpl.render(context)
        
        # Crear directorio temporal si no existe
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Guardar DOCX temporal
        tmp_docx = os.path.join(temp_dir, f"financiamiento_cotiza_{fin.id}.docx")
        tpl.save(tmp_docx)
        
        # Convertir a PDF
        # Nombre del archivo similar a carta de intención
        cliente_nombre = fin.nombre_cliente.replace(' ', '_')
        pdf_filename = f"financiamiento_cotiza_{cliente_nombre}_{fin.id}.pdf"
        tmp_pdf = os.path.join(temp_dir, pdf_filename)
        
        success = convert_docx_to_pdf(tmp_docx, tmp_pdf)
        
        if success and os.path.exists(tmp_pdf):
            # Leer el PDF y enviarlo como respuesta
            with open(tmp_pdf, 'rb') as pdf_file:
                response = HttpResponse(pdf_file.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
                
                # Limpiar archivos temporales después de enviar
                try:
                    os.remove(tmp_docx)
                    os.remove(tmp_pdf)
                except:
                    pass  # Ignorar errores de limpieza
                
                return response
        else:
            # Si falla la conversión a PDF, enviar el DOCX
            with open(tmp_docx, 'rb') as docx_file:
                response = HttpResponse(
                    docx_file.read(), 
                    content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                )
                response['Content-Disposition'] = f'attachment; filename="financiamiento_cotiza_{fin.id}.docx"'
                
                # Limpiar archivo temporal
                try:
                    os.remove(tmp_docx)
                except:
                    pass
                
                return response
    
    except Exception as e:
        # En caso de error, retornar mensaje
        import traceback
        error_details = traceback.format_exc()
        return HttpResponse(f"Error al generar el documento: {str(e)}\n\nDetalles:\n{error_details}", status=500)
    
def calcular_distribucion_meses_fuertes(total_meses, cantidad_meses_fuertes, frecuencia=None):
    """
    Replica exactamente la lógica de JavaScript para Commeta.
    """
    # Caso especial: si todos los meses son fuertes
    if cantidad_meses_fuertes >= total_meses:
        return list(range(1, total_meses + 1))
    
    if frecuencia:
        # Distribución con frecuencia fija
        meses_fuertes = []
        mes_actual = frecuencia
        while len(meses_fuertes) < cantidad_meses_fuertes and mes_actual <= total_meses:
            meses_fuertes.append(mes_actual)
            mes_actual += frecuencia
        return meses_fuertes
    else:
        # Distribución automática (equidistante)
        if cantidad_meses_fuertes == 0:
            return []
        
        espaciado = max(1, total_meses // cantidad_meses_fuertes)
        meses_fuertes = []
        
        # Comenzar desde el primer mes disponible
        for i in range(cantidad_meses_fuertes):
            mes = min((i * espaciado) + 1, total_meses)
            meses_fuertes.append(mes)
        
        # Eliminar duplicados y ordenar
        meses_unicos = sorted(set(meses_fuertes))
        meses_filtrados = [mes for mes in meses_unicos if mes <= total_meses]
        
        # Si nos faltan meses fuertes, agregar al final
        meses_finales = list(meses_filtrados)
        while len(meses_finales) < cantidad_meses_fuertes and meses_finales[-1] < total_meses:
            nuevo_mes = min(meses_finales[-1] + 1, total_meses)
            if nuevo_mes not in meses_finales:
                meses_finales.append(nuevo_mes)
        
        return sorted(meses_finales[:cantidad_meses_fuertes])
    
# En financiamiento/views.py (junto a tu builder normal)

def build_financiamiento_commeta_cotiza_context(fin_commeta, request=None):
    """
    Context para Tabla de Financiamiento Commeta (cotización)
    """
    # Obtenemos el financiamiento base
    fin = fin_commeta.financiamiento
    
    # 1) Fecha actual
    hoy = date.today()
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    # 2) Cálculos iniciales
    resta_apartado = float(fin.precio_lote) - float(fin.apartado)
    resta_enganche = resta_apartado - float(fin.enganche or 0)
    
    # 3) Determinar meses fuertes si aplica
    meses_fuertes = []
    if fin_commeta.tipo_esquema == 'meses_fuertes':
        if fin_commeta.usar_meses_especificos and fin_commeta.meses_fuertes_calculados:
            meses_fuertes = fin_commeta.meses_fuertes_calculados
        else:
            meses_fuertes = calcular_distribucion_meses_fuertes(
                total_meses=fin.num_mensualidades,
                cantidad_meses_fuertes=fin_commeta.cantidad_meses_fuertes,
                frecuencia=fin_commeta.frecuencia_meses_fuertes
            )

    # 4) Determinar montos según esquema
    es_meses_fuertes = fin_commeta.tipo_esquema == 'meses_fuertes'
    
    # Para ABONO_NORMAL:
    if es_meses_fuertes:
        # Esquema meses fuertes: usar monto_mensualidad_normal de FinanciamientoCommeta
        abono_normal = float(fin_commeta.monto_mensualidad_normal) if fin_commeta.monto_mensualidad_normal else 0
    else:
        # Esquema mensualidades fijas: usar monto_mensualidad del Financiamiento base
        abono_normal = float(fin.monto_mensualidad) if fin.monto_mensualidad else 0
    
    # Para ABONO_FUERTE: solo aplica para meses fuertes
    if es_meses_fuertes:
        abono_fuerte = float(fin_commeta.monto_mes_fuerte) if fin_commeta.monto_mes_fuerte else 0
    else:
        abono_fuerte = 0  # No aplica para mensualidades fijas
    
    # Para PERIODO_FUERTE: solo aplica para meses fuertes
    if es_meses_fuertes:
        periodo_fuerte = fin_commeta.frecuencia_meses_fuertes
    else:
        periodo_fuerte = None
    
    # 4) Generar lista de pagos según esquema
    pagos = []
    saldo_actual = resta_enganche
    fecha_pago = fin.fecha_primer_pago
    
    for i in range(1, fin.num_mensualidades + 1):
        es_mes_fuerte = i in meses_fuertes
        
        # Determinar monto de la cuota según esquema
        if fin_commeta.tipo_esquema == 'mensualidades_fijas':
            if i == fin.num_mensualidades and fin.monto_pago_final:
                cuota = float(fin.monto_pago_final)
            elif i == fin.num_mensualidades and not fin.monto_pago_final:
                cuota = saldo_actual
            else:
                cuota = float(fin.monto_mensualidad)
        else:  # meses_fuertes
            if i == fin.num_mensualidades and fin.monto_pago_final:
                cuota = float(fin.monto_pago_final)
            elif es_mes_fuerte:
                cuota = float(fin_commeta.monto_mes_fuerte)
            else:
                cuota = float(fin_commeta.monto_mensualidad_normal)
        
        saldo_final = max(0, saldo_actual - cuota)
        
        # Asegurarnos de que todos los valores sean strings válidos
        pagos.append({
            'numero': str(i),  # Convertir a string
            'fecha': fecha_pago.strftime("%d/%m/%Y") if fecha_pago else '',
            'saldo_inicial': fmt_money(saldo_actual),
            'cuota': fmt_money(cuota),
            'saldo_final': fmt_money(saldo_final),
        })
        
        saldo_actual = saldo_final
        if fecha_pago:
            try:
                if fecha_pago.month == 12:
                    fecha_pago = fecha_pago.replace(year=fecha_pago.year + 1, month=1)
                else:
                    fecha_pago = fecha_pago.replace(month=fecha_pago.month + 1)
            except:
                pass
    
    # 5) Obtener nombre del vendedor
    nombre_vendedor = "Administración"
    if request and request.user.is_authenticated:
        if request.user.first_name and request.user.last_name:
            nombre_vendedor = f"{request.user.first_name} {request.user.last_name}"
        elif request.user.first_name:
            nombre_vendedor = request.user.first_name
        else:
            nombre_vendedor = request.user.username
        nombre_vendedor = nombre_vendedor.upper()

    superfici = fin.lote.superficie_m2
    
    # Obtener zona de Commeta - Asegurar que sea string
    zona_display = ""
    if fin_commeta.configuracion_original:
        zona_display = fin_commeta.configuracion_original.get_zona_display()
    
    # Calcular precio por metro - Asegurar división por cero
    if float(superfici) > 0:
        precio_metro = float(fin.precio_lote) / float(superfici)
        precio_metro_str = fmt_money(precio_metro)
    else:
        precio_metro_str = '0.00'
    
    # 6) Construir contexto con validación de tipos
    context = {
        # Fechas (asegurar strings)
        'FECHA_FINANCIAMIENTO': f"{hoy.day} de {meses[hoy.month-1]} de {hoy.year}",
        'FECHA_APARTADO': fin.creado_en.strftime("%d/%m/%Y") if fin.creado_en else hoy.strftime("%d/%m/%Y"),
        'FECHA_ENGANCHE': fin.fecha_enganche.strftime("%d/%m/%Y") if fin.fecha_enganche else '',
        
        # Datos del lote y cliente
        'NOMBRE_CLIENTE': str(fin.nombre_cliente).upper() if fin.nombre_cliente else '',
        'NOMBRE_VENDEDOR': str(nombre_vendedor),
        'NOMBRE_PROYECTO': str(fin.lote.proyecto.nombre).upper() if fin.lote.proyecto.nombre else '',
        'IDENTIFICADOR_LOTE': str(fin.lote.identificador) if fin.lote.identificador else '',
        'ZONA': str(zona_display),
        'METROS_CUADRADOS': str(superfici),
        'PRECIO_METRO': str(precio_metro_str),
        
        # Montos financiamiento (asegurar strings)
        'PRECIO_LOTE': fmt_money(fin.precio_lote) if fin.precio_lote else '0.00',
        'APARTADO': fmt_money(fin.apartado) if fin.apartado else '0.00',
        'ENGANCHE': fmt_money(fin.enganche) if fin.enganche else '0.00',
        'TOTAL_FIN': fmt_money(resta_enganche),
        'NUM_MESES': str(fin.num_mensualidades) if fin.num_mensualidades else '0',
        
        # Datos específicos Commeta
        'ABONO_FUERTE': fmt_money(abono_fuerte) if es_meses_fuertes else '0.00',
        'PERIODO_FUERTE': fin.num_mensualidades,
        'ABONO_NORMAL': fmt_money(abono_normal),
        
        # Cálculos intermedios
        'RESTA_APARTADO': fmt_money(resta_apartado),
        'RESTA_ENGANCHE': fmt_money(resta_enganche),
        
        # Lista de pagos
        'pagos': pagos,
    }

    return context

# En financiamiento/views.py (junto a descargar_financiamiento_cotiza_pdf)

def descargar_financiamiento_commeta_cotiza_pdf(request, pk):
    """
    Vista para descargar un financiamiento Commeta (cotización) en PDF
    Copia de la vista normal, pero usa builder y template de Commeta
    """
 
    try:
        # Obtener el financiamiento Commeta
        from .models import FinanciamientoCommeta
        fin_commeta = get_object_or_404(FinanciamientoCommeta, pk=pk)
        
        print(f"✅ FinanciamientoCommeta obtenido: {fin_commeta.id}")
        
        # Ruta a la plantilla
        tpl_path = os.path.join(settings.BASE_DIR, 'pdfs/templates/pdfs/cotiza_financia_c.docx')
        print(f"📄 Ruta del template: {tpl_path}")
        
        # Verificar que la plantilla existe
        if not os.path.exists(tpl_path):
            print("❌ Template no existe")
            return HttpResponse("Plantilla Commeta no encontrada", status=500)
        
        # Verificar tamaño del archivo
        file_size = os.path.getsize(tpl_path)
        print(f"📏 Tamaño del template: {file_size} bytes")
        # Generar contexto
        context = build_financiamiento_commeta_cotiza_context(fin_commeta, request=request)
        print(f"✅ Contexto generado con {len(context)} campos")
        
        # Debug: mostrar algunos valores del contexto
        print("🔍 Muestra del contexto:")
        for key, value in list(context.items())[:10]:  # Primeros 10 items
            if isinstance(value, (str, int, float)):
                print(f"   {key}: {value}")
            elif isinstance(value, list):
                print(f"   {key}: lista con {len(value)} elementos")
        
        # Intentar cargar el template
        print("🔄 Intentando cargar template...")

        try:
            tpl = DocxTemplate(tpl_path)
            print("✅ Template cargado exitosamente")
        except Exception as e:
            print(f"❌ Error al cargar template: {str(e)}")
            # Intentar con un template simple
            simple_tpl_path = os.path.join(settings.BASE_DIR, 'pdfs/templates/pdfs/cotiza_financia_n.docx')
            if os.path.exists(simple_tpl_path):
                print("🔄 Intentando con template normal...")
                tpl = DocxTemplate(simple_tpl_path)
            else:
                raise
        
        # Renderizar
        print("🔄 Renderizando...")
        tpl.render(context)
        print("✅ Renderizado exitoso")
        
        # Crear directorio temporal si no existe
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Guardar DOCX temporal
        tmp_docx = os.path.join(temp_dir, f"financiamiento_commeta_cotiza_{fin_commeta.id}.docx")
        tpl.save(tmp_docx)
        
        # Convertir a PDF
        cliente_nombre = fin_commeta.financiamiento.nombre_cliente.replace(' ', '_')
        pdf_filename = f"financiamiento_commeta_cotiza_{cliente_nombre}_{fin_commeta.id}.pdf"
        tmp_pdf = os.path.join(temp_dir, pdf_filename)
        
        success = convert_docx_to_pdf(tmp_docx, tmp_pdf)
        
        if success and os.path.exists(tmp_pdf):
            with open(tmp_pdf, 'rb') as pdf_file:
                response = HttpResponse(pdf_file.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
                
                try:
                    os.remove(tmp_docx)
                    os.remove(tmp_pdf)
                except:
                    pass
                
                return response
        else:
            # Si falla la conversión a PDF, enviar el DOCX
            with open(tmp_docx, 'rb') as docx_file:
                response = HttpResponse(
                    docx_file.read(), 
                    content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                )
                response['Content-Disposition'] = f'attachment; filename="financiamiento_commeta_cotiza_{fin_commeta.id}.docx"'
                
                try:
                    os.remove(tmp_docx)
                except:
                    pass
                
                return response
    
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        error_details = traceback.format_exc()
        print(f"📋 Traceback completo:\n{error_details}")
        return HttpResponse(f"Error al generar el documento: {str(e)}", status=500)

