from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import Financiamiento, CartaIntencion
from .forms import FinanciamientoForm, CartaIntencionForm
from core.models import Lote  # Importamos el modelo Lote
from django.http import JsonResponse
from django.views.decorators.http import require_GET


class FinanciamientoListView(ListView):
    model = Financiamiento
    template_name = "financiamiento/list.html"
    context_object_name = "planes"
    
    def get_queryset(self):
        # Opcional: puedes filtrar o ordenar los planes aquí
        return Financiamiento.objects.all().order_by('-creado_en')


class FinanciamientoCreateView(CreateView):
    model = Financiamiento
    form_class = FinanciamientoForm
    template_name = "financiamiento/form.html"
    success_url = reverse_lazy('financiamiento:list')

    def form_valid(self, form):
        # Guardamos primero el financiamiento
        response = super().form_valid(form)
        
        # Obtenemos el lote asociado al financiamiento
        lote = form.cleaned_data['lote']
        es_cotizacion = form.cleaned_data.get('es_cotizacion', False)
        
        # SOLO marcar el lote como inactivo si NO es una cotización
        if not es_cotizacion:
            lote.activo = False
            lote.save()
            messages.success(self.request, f"Financiamiento creado exitosamente. El lote {lote.identificador} ha sido marcado como inactivo.")
        else:
            messages.success(self.request, f"Cotización creada exitosamente. El lote {lote.identificador} permanece disponible.")
        
        return response

    def form_invalid(self, form):
        # Opcional: manejar errores de formulario
        messages.error(self.request, "Por favor corrige los errores en el formulario.")
        return super().form_invalid(form)


class FinanciamientoUpdateView(UpdateView):
    model = Financiamiento
    form_class = FinanciamientoForm
    template_name = "financiamiento/form.html"
    success_url = reverse_lazy('financiamiento:list')

    def form_valid(self, form):
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
    superficie = calcular_superficie(lote.norte, lote.sur, lote.este, lote.oeste)
    
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
