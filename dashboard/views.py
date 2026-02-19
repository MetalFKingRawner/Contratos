# dashboard/views.py
from django.views.generic import View
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from workflow.models import Tramite  # Ajusta al path real de tu modelo
from financiamiento.models import Financiamiento, CartaIntencion, FinanciamientoCommeta  # Ajusta import según tu estructura
from core.models import Cliente, ConfiguracionCommeta  # o donde tengas definido Cliente
from core.models import Vendedor, Propietario
from core.models import Proyecto, Lote, Beneficiario
from django.db.models import Prefetch
from core.forms import ClienteForm, VendedorForm, BeneficiarioForm  # lo definimos a continuación
from django.urls import reverse_lazy
from django.views.generic import UpdateView
from django.shortcuts import render
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest, HttpResponseRedirect, JsonResponse, HttpResponse
from django.urls import reverse
from .forms import PropietarioForm, ProyectoForm,LoteForm, TramiteForm
from django.db.models import Q
from financiamiento.forms import FinanciamientoForm, CartaIntencionForm
from django.contrib.auth.models import User
from financiamiento.models import CartaIntencion
#class DashboardHomeView(TemplateView):
#    template_name = 'dashboard/home.html'

import os
import io
from workflow.docs import DOCUMENTOS
from pdfs.utils import convert_docx_to_pdf 
from docxtpl import DocxTemplate
from django.conf import settings
from .utils import crear_usuario_para_vendedor
from django.contrib import messages
from financiamiento.views import build_carta_intencion_from_instance
from pdfs.utils import convert_docx_to_pdf

class DownloadDocumentView(View):
    """Vista para descargar documentos individuales en Word o PDF."""
    
    def get(self, request, pk, document_type, format):
        # 1. Obtener el trámite
        tramite = get_object_or_404(Tramite, pk=pk)
        
        # 2. Para el caso especial del contrato, determinar el tipo específico
        if document_type == 'contrato':
            fin = tramite.financiamiento
            regime = fin.lote.proyecto.tipo_contrato.lower()
            pago = fin.tipo_pago
            has_second_client = tramite.cliente_2 is not None

            if 'propiedad definitiva' in regime:
                if has_second_client:
                    if pago == 'contado':
                        document_type = 'contrato_definitiva_contado_varios'
                    else:
                       document_type = 'contrato_definitiva_pagos_varios'
                else:
                    if pago == 'contado':
                        document_type = 'contrato_definitiva_contado'
                    else:
                        document_type = 'contrato_definitiva_pagos'
            elif 'pequeña propiedad' in regime:
                if has_second_client:
                    if pago == 'contado':
                        document_type = 'contrato_propiedad_contado_varios'
                    else:
                        document_type = 'contrato_propiedad_pagos_varios'
                else:
                    if pago == 'contado':
                        document_type = 'contrato_propiedad_contado'
                    else:
                        document_type = 'contrato_propiedad_pagos'
            elif 'ejido' in regime:
                # ejidal o comunal
                if has_second_client:
                    if pago == 'contado':
                        document_type = 'contrato_ejidal_contado_varios'
                    else:
                        document_type = 'contrato_ejidal_pagos_varios'
                else:
                    if pago == 'contado':
                        document_type = 'contrato_ejidal_contado'
                    else:
                        document_type = 'contrato_ejidal_pagos'
            else:
                if fin.es_commeta:
                    if has_second_client:
                        if pago == 'contado':
                            document_type = 'contrato_canario_contado_varios'
                        else:
                            document_type = 'contrato_commeta_pagos_varios'
                    else:
                        if pago == 'contado':
                            document_type = 'contrato_canario_contado'
                        else:
                            document_type = 'contrato_commeta_pagos'
                else:
                    if has_second_client:
                        if pago == 'contado':
                            document_type = 'contrato_canario_contado_varios'
                        else:
                            document_type = 'contrato_canario_pagos_varios'
                    else:
                        if pago == 'contado':
                            document_type = 'contrato_canario_contado'
                        else:
                            document_type = 'contrato_canario_pagos'
        
        # 3. Para plan_financiamiento, si no existe en DOCUMENTOS, usar uno por defecto
        if document_type == 'plan_financiamiento' and document_type not in DOCUMENTOS:
            # Puedes mapearlo a un documento existente o manejarlo de forma especial
            document_type = 'solicitud_contrato'  # Ejemplo, ajusta según necesites
            
        # 4. Verificar que el document_type esté en DOCUMENTOS
        if document_type not in DOCUMENTOS:
            return HttpResponse("Tipo de documento no válido", status=404)
            
        doc_info = DOCUMENTOS[document_type]
        
        # 5. Obtener los datos necesarios del trámite
        fin = tramite.financiamiento
        cli = tramite.cliente
        fecha = tramite.creado_en
        # Obtener la persona correcta según el tipo
        if tramite.persona_tipo == 'vendedor':
            ven = tramite.vendedor
        else:
            ven = tramite.propietario
        cli2 = tramite.cliente_2  # Segundo cliente
        
        # Obtener cláusulas especiales de la base de datos
        clausulas_adicionales = {}
        if hasattr(tramite, 'clausulas_especiales'):
            clausulas_db = tramite.clausulas_especiales
            clausulas_adicionales = {
                'pago': clausulas_db.clausula_pago,
                'deslinde': clausulas_db.clausula_deslinde,
                'promesa': clausulas_db.clausula_promesa,
            }
        
        # 6. Construir el contexto
        builder = doc_info['builder']
        tpl_path = os.path.join(settings.BASE_DIR, doc_info['plantilla'])
        tpl = DocxTemplate(tpl_path)
        
        # Manejo especial para el documento de financiamiento
        if document_type == 'financiamiento':
            try:
                if tramite.es_commeta:
                    # CORRECCIÓN: obtener_detalle_commeta es una propiedad, NO un método
                    fin_commeta = tramite.obtener_detalle_commeta  # SIN PARÉNTESIS
                    print(f"📊 Dashboard - Generando financiamiento Commeta, esquema: {fin_commeta.tipo_esquema if fin_commeta else 'N/A'}")
                    
                    # Llamar al builder con parámetros Commeta
                    context = builder(
                        fin, cli, ven, 
                        request=request, 
                        tpl=tpl, 
                        firma_data=tramite.firma_cliente,
                        clausulas_adicionales=clausulas_adicionales,
                        cliente2=cli2,
                        tramite=tramite,
                        fecha=fecha,
                        is_commeta=True,
                        fin_commeta=fin_commeta
                    )
                else:
                    # Llamar al builder para financiamiento normal
                    context = builder(
                        fin, cli, ven, 
                        request=request, 
                        tpl=tpl, 
                        firma_data=tramite.firma_cliente,
                        clausulas_adicionales=clausulas_adicionales,
                        cliente2=cli2,
                        tramite=tramite,
                        fecha=fecha,
                        is_commeta=False,
                        fin_commeta=None
                    )
            except Exception as e:
                print(f"❌ Error en builder de financiamiento (dashboard): {str(e)}")
                import traceback
                traceback.print_exc()
                # Fallback a la versión simple
                try:
                    context = builder(
                        fin, cli, ven, 
                        request=request, 
                        tpl=tpl, 
                        firma_data=tramite.firma_cliente,
                        fecha=fecha
                    )
                except TypeError:
                    context = builder(fin, cli, ven, request=request, tpl=tpl, firma_data=tramite.firma_cliente)
        else:
            # Para los otros documentos, usar el método existente
            try:
                context = builder(
                    fin, cli, ven, 
                    cliente2=cli2,
                    request=request, 
                    tpl=tpl, 
                    firma_data=tramite.firma_cliente, 
                    clausulas_adicionales=clausulas_adicionales,
                    tramite=tramite,
                    fecha=fecha
                )
            except TypeError as e:
                # Si el builder no acepta cliente2, intentar sin él
                try:
                    context = builder(
                        fin, cli, ven, 
                        request=request, 
                        tpl=tpl, 
                        firma_data=tramite.firma_cliente, 
                        clausulas_adicionales=clausulas_adicionales,
                        tramite=tramite,
                        fecha=fecha
                    )
                except TypeError:
                    try:
                        # Versión mínima con Trámite (Ej. Solicitud de contrato)
                        context = builder(fin, cli, ven, request=request, tpl=tpl, firma_data=tramite.firma_cliente, tramite=tramite, fecha=fecha)
                    except TypeError:
                        try:
                            # Versión con fecha pero sin tramite
                            context = builder(fin, cli, ven, request=request, tpl=tpl, firma_data=tramite.firma_cliente, fecha=fecha)
                        except TypeError:
                            #Versión sin Trámite ni fecha
                            context = builder(fin, cli, ven, request=request, tpl=tpl, firma_data=tramite.firma_cliente)

        
        # 7. Generar el documento Word
        output = io.BytesIO()
        tpl.render(context)
        tpl.save(output)
        output.seek(0)
        
        # 8. Si el formato es Word, devolver el docx
        if format == 'word':
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            
            # Nombre del archivo más descriptivo
            if document_type == 'financiamiento':
                cliente_nombre = cli.nombre_completo.replace(' ', '_')
                tipo = 'commeta' if tramite.es_commeta else 'normal'
                filename = f"tabla_financiamiento_{tipo}_{cliente_nombre}.docx"
            else:
                filename = f"{document_type}.docx"
                
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        
        # 9. Si el formato es PDF, convertir el Word a PDF y devolverlo
        elif format == 'pdf':
            # Guardar temporalmente el docx
            temp_docx_path = os.path.join(settings.MEDIA_ROOT, 'temp', f"{document_type}.docx")
            os.makedirs(os.path.dirname(temp_docx_path), exist_ok=True)
            with open(temp_docx_path, 'wb') as f:
                f.write(output.getvalue())
            
            # Convertir a PDF
            temp_pdf_path = os.path.join(settings.MEDIA_ROOT, 'temp', f"{document_type}.pdf")
            success = convert_docx_to_pdf(temp_docx_path, temp_pdf_path)
            
            if success:
                # Leer el PDF y devolverlo
                with open(temp_pdf_path, 'rb') as f:
                    pdf_data = f.read()
                
                # Nombre del archivo más descriptivo
                if document_type == 'financiamiento':
                    cliente_nombre = cli.nombre_completo.replace(' ', '_')
                    tipo = 'commeta' if tramite.es_commeta else 'normal'
                    filename = f"tabla_financiamiento_{tipo}_{cliente_nombre}.pdf"
                else:
                    filename = f"{document_type}.pdf"
                    
                response = HttpResponse(pdf_data, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                
                # Limpiar archivos temporales
                try:
                    os.remove(temp_docx_path)
                    os.remove(temp_pdf_path)
                except:
                    pass
                    
                return response
            else:
                # Si falla la conversión, devolver el Word
                response = HttpResponse(
                    output.getvalue(),
                    content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                )
                response['Content-Disposition'] = f'attachment; filename="{document_type}.docx"'
                return response
        
        else:
            return HttpResponse("Formato no válido", status=400)

class TramiteListView(ListView):
    """Listado de Trámites."""
    model = Tramite
    context_object_name = 'tramites'
    paginate_by = 5
    ordering = ['-creado_en']  # Ordenar por fecha de creación descendente

    def get_template_names(self):
        # Si es una solicitud HTMX, devolvemos un template parcial
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/tramites_list_partial.html']
        return ['dashboard/tramites_list.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Obtener TODOS los usuarios (no solo los que tienen trámites)
        todos_los_usuarios = User.objects.exclude(username='admin').select_related('vendedor')
        
        # Crear lista de usuarios para el filtro con el formato correcto
        usuarios_filtro = []
        for usuario in todos_los_usuarios:
            # Verificar si tiene un vendedor asociado
            if hasattr(usuario, 'vendedor') and usuario.vendedor:
                nombre = f"🧑‍💼 {usuario.vendedor.nombre_completo}"
            else:
                # Para usuarios sin vendedor (staff), usar el username
                if usuario.first_name and usuario.last_name:
                    nombre = f"👨‍💻 {usuario.first_name} {usuario.last_name} ({usuario.username})"
                else:
                    nombre = f"👨‍💻 {usuario.username}"
            
            usuarios_filtro.append({
                'id': usuario.id,
                'nombre': nombre
            })
        
        # Ordenar alfabéticamente por nombre
        usuarios_filtro.sort(key=lambda x: x['nombre'].lower())

        # NUEVO: Estadísticas de firmas
        total_tramites = Tramite.objects.count()
        # Contar trámites con firmas pendientes usando la propiedad del modelo
        tramites_con_firmas_pendientes = 0
        for tramite in Tramite.objects.all():
            if tramite.tiene_firmas_pendientes:
                tramites_con_firmas_pendientes += 1

        context.update({
            'total_tramites': total_tramites,
            'tramites_activos': total_tramites,
            'tramites_con_firmas_pendientes': tramites_con_firmas_pendientes,
            'usuarios_filtro': usuarios_filtro,
            'filtro_usuario_actual': self.request.GET.get('usuario', ''),
            'termino_busqueda_actual': self.request.GET.get('search', ''),
        })

        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        # Optimizar consultas relacionadas
        queryset = queryset.select_related(
            'cliente', 
            'cliente_2',  # Para segundo cliente
            'financiamiento', 
            'financiamiento__lote',
            'usuario_creador',
            'vendedor',
            'propietario',
            'beneficiario_1',  # Para beneficiarios
            'beneficiario_2'
        ).prefetch_related(
            'usuario_creador__vendedor'
        )

        # Obtener parámetros de filtro
        usuario_id = self.request.GET.get('usuario')
        search_term = self.request.GET.get('search')
        
        # Aplicar filtro por usuario si se especificó
        if usuario_id:
            queryset = queryset.filter(usuario_creador_id=usuario_id)
        
        # Aplicar búsqueda si se especificó
        if search_term:
            # Buscar por ID de trámite o nombre de cliente
            try:
                # Intentar convertir a número para búsqueda por ID
                tramite_id = int(search_term)
                queryset = queryset.filter(id=tramite_id)
            except ValueError:
                # Búsqueda por nombre de cliente
                queryset = queryset.filter(cliente__nombre_completo__icontains=search_term)
        
        # Si hay filtro o búsqueda, desactivar paginación
        if usuario_id or search_term:
            self.paginate_by = None

        return queryset

class TramiteGenerateLinksView(View):
    """Genera los links de firma para un trámite"""
    
    def post(self, request, pk):
        tramite = get_object_or_404(Tramite, pk=pk)
        
        try:
            links_generados = tramite.generar_links_firma()
            
            # Recargar el trámite para obtener los datos actualizados
            tramite.refresh_from_db()
            
            # En lugar de renderizar un fragmento, redirigir al detalle
            if request.headers.get('HX-Request'):
                # Para HTMX, hacer un redirect que recargue el contenido
                response = HttpResponse()
                response['HX-Redirect'] = reverse('dashboard:tramite_detail', kwargs={'pk': pk})
                return response
            else:
                messages.success(request, f'Links generados: {", ".join(links_generados)}')
                return redirect('dashboard:tramite_detail', pk=pk)
            
        except Exception as e:
            if request.headers.get('HX-Request'):
                return render(request, 'dashboard/partials/firmas_section.html', {
                    'tramite': tramite,
                    'messages': [{'message': f'Error generando links: {str(e)}', 'tags': 'error'}]
                }, status=400)
            else:
                messages.error(request, f'Error generando links: {str(e)}')
                return redirect('dashboard:tramite_detail', pk=pk)

class TramiteDetailView(DetailView):
    """Detalle de un Trámite."""
    model = Tramite
    template_name = 'dashboard/tramites_detail.html'
    context_object_name = 'tramite'

    def get_template_names(self):
        # Si es una solicitud HTMX, devolvemos un template parcial
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/tramites_detail_partial.html']
        return [self.template_name]

    def get_queryset(self):
        # OPTIMIZAR: Incluir todas las relaciones necesarias para las firmas
        return super().get_queryset().select_related(
            'cliente',
            'cliente_2',  # Para segundo cliente
            'financiamiento',
            'financiamiento__lote',
            'usuario_creador',
            'vendedor',
            'propietario',
            'beneficiario_1',  # Para beneficiarios
            'beneficiario_2'
        ).prefetch_related(
            'usuario_creador__vendedor'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tramite = self.object
        
        # Asegurarnos de que el método obtener_urls_firma_completas esté disponible
        if hasattr(tramite, 'obtener_urls_firma_completas'):
            context['urls_firma_completas'] = tramite.obtener_urls_firma_completas(self.request)
        else:
            # Fallback por si el método no existe
            context['urls_firma_completas'] = {}
            
        return context

class TramiteCreateView(CreateView):
    model = Tramite
    form_class = TramiteForm  # Necesitarás crear este formulario
    template_name = 'dashboard/partials/tramite_form.html'

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('HX-Request'):
            return TramiteListView.as_view()(self.request._request)
        return redirect('dashboard:tramite_list')

class TramiteUpdateView(UpdateView):
    model = Tramite
    form_class = TramiteForm
    template_name = 'dashboard/partials/tramite_form.html'

    def form_valid(self, form):
        # Capturar el estado ANTES de guardar para detectar cambios
        tramite_antes = self.get_object()
        estado_antes = self._capturar_estado_firmantes(tramite_antes)
        # Guardar el formulario (que incluye las cláusulas)
        self.object = form.save()

        # Detectar cambios en firmantes y regenerar links si es necesario
        cambios = self._detectar_cambios_firmantes(estado_antes, self.object)
        if cambios:
            try:
                links_generados = self.object.generar_links_firma()
                print(f"✅ Links regenerados por cambios en: {', '.join(cambios)}")
            except Exception as e:
                print(f"❌ Error regenerando links: {e}")
        
        if self.request.headers.get('HX-Request'):
            # Devolver el detalle actualizado para HTMX
            return render(self.request, 'dashboard/partials/tramites_detail_partial.html', 
                         {'tramite': self.object})
        return redirect('dashboard:tramite_detail', pk=self.object.pk)
    
    def _capturar_estado_firmantes(self, tramite):
        """Captura el estado actual de los firmantes para comparación"""
        return {
            'cliente_2_id': tramite.cliente_2_id,
            'beneficiario_1_id': tramite.beneficiario_1_id,
            'beneficiario_2_id': tramite.beneficiario_2_id,
            'testigo_1_nombre': tramite.testigo_1_nombre,
            'testigo_2_nombre': tramite.testigo_2_nombre,
        }

    def _detectar_cambios_firmantes(self, estado_antes, tramite_despues):
        """Detecta cambios en los firmantes y retorna lista de campos modificados"""
        cambios = []
        
        if estado_antes['cliente_2_id'] != tramite_despues.cliente_2_id:
            cambios.append('segundo_cliente')
        
        if estado_antes['beneficiario_1_id'] != tramite_despues.beneficiario_1_id:
            cambios.append('beneficiario_1')
        
        if estado_antes['beneficiario_2_id'] != tramite_despues.beneficiario_2_id:
            cambios.append('beneficiario_2')
        
        if estado_antes['testigo_1_nombre'] != tramite_despues.testigo_1_nombre:
            cambios.append('testigo_1')
        
        if estado_antes['testigo_2_nombre'] != tramite_despues.testigo_2_nombre:
            cambios.append('testigo_2')
        
        return cambios

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('HX-Request'):
            # Devolver el formulario con errores para HTMX
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Asegurarse de que el formulario de cláusulas esté en el contexto
        if 'form' not in context:
            context['form'] = self.get_form()
        return context
    

class TramiteDeleteView(DeleteView):
    model = Tramite
    template_name = 'dashboard/partials/tramite_confirm_delete.html'
    success_url = reverse_lazy('dashboard:tramite_list')

    def delete(self, request, *args, **kwargs):
        try:
            # Guardar información del trámite para el mensaje
            self.object = self.get_object()
            tramite_id = self.object.id
            cliente_nombre = self.object.cliente.nombre_completo
            
            response = super().delete(request, *args, **kwargs)
            
            # Mensaje de éxito
            messages.success(request, f'Trámite #{tramite_id} de {cliente_nombre} eliminado correctamente.')
            
            if request.headers.get('HX-Request'):
                return TramiteListView.as_view()(request._request)
            return response
            
        except Exception as e:
            # Manejo de errores
            messages.error(request, f'Error al eliminar el trámite: {str(e)}')
            
            if request.headers.get('HX-Request'):
                # Si hay error, regresar al detalle del trámite
                return redirect('dashboard:tramite_detail', pk=kwargs.get('pk'))
            return redirect('dashboard:tramite_detail', pk=kwargs.get('pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Añadir información adicional para el template
        context['tiene_firmas_pendientes'] = self.object.tiene_firmas_pendientes if self.object else False
        context['firmas_pendientes_count'] = len(self.object.firmas_pendientes) if self.object else 0
        return context

class FinanciamientoListView(ListView):
    """Listado de planes de financiamiento."""
    model = Financiamiento
    context_object_name = 'planes'
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_financiamientos'] = Financiamiento.objects.count()
        context['financiamientos_activos'] = Financiamiento.objects.count()  # Ajusta según tu modelo
        return context

    def get_template_names(self):
        # Si HTMX, devolvemos solo el fragmento
        if self.request.headers.get('Hx-Request'):
            return ['dashboard/partials/financiamientos_list_partial.html']
        # Si no, la vista completa
        return ['dashboard/financiamiento_list.html']
    
    def get_queryset(self):
        # ordena siempre por pk/ID ascendente
        return super().get_queryset().order_by('id')


class FinanciamientoDetailView(DetailView):
    """Detalle de un plan de financiamiento."""
    model = Financiamiento
    template_name = 'dashboard/partials/financiamientos_detail.html'
    context_object_name = 'plan'
    
    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return 'dashboard/partials/financiamientos_detail.html'
        return 'dashboard/financiamientos_detail.html'

class FinanciamientoCreateView(CreateView):
    model = Financiamiento
    form_class = FinanciamientoForm
    template_name = 'dashboard/partials/financiamiento_form.html'

    def get_success_url(self):
        return reverse_lazy('dashboard:financiamiento_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        # Obtenemos el lote asociado al financiamiento
        lote = form.cleaned_data['lote']
        
        # Cambiamos su estado a inactivo
        lote.activo = False
        lote.save()

        if self.request.headers.get('HX-Request'):
            # Devolver la lista actualizada
            return render(self.request, 'dashboard/partials/financiamientos_list_partial.html', 
                         {'planes': Financiamiento.objects.all().order_by('id')})
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'create'
        return context


class FinanciamientoUpdateView(UpdateView):
    model = Financiamiento
    form_class = FinanciamientoForm
    template_name = 'dashboard/partials/financiamiento_form.html'

    def get_success_url(self):
        return reverse_lazy('dashboard:financiamiento_list')

    def form_valid(self, form):
        # CAMBIO IMPORTANTE: Lógica mejorada para lotes
        lote_anterior = self.object.lote  # El lote que tenía antes de la edición
        lote_nuevo = form.cleaned_data['lote']  # El lote seleccionado en el formulario
        
        response = super().form_valid(form)
        
        # Si cambió de lote, activar el anterior y desactivar el nuevo
        if lote_anterior.pk != lote_nuevo.pk:
            # Activar el lote anterior (ya no está financiado)
            lote_anterior.activo = True
            lote_anterior.save()
            
            # Desactivar el nuevo lote
            lote_nuevo.activo = False
            lote_nuevo.save()
        else:
            # Si es el mismo lote, mantenerlo inactivo
            lote_nuevo.activo = False
            lote_nuevo.save()

        if self.request.headers.get('HX-Request'):
            # Devolver el detalle actualizado
            return render(self.request, 'dashboard/partials/financiamientos_detail.html', 
                         {'plan': self.object})
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'edit'
        return context


class FinanciamientoDeleteView(DeleteView):
    model = Financiamiento
    success_url = reverse_lazy('dashboard:financiamiento_list')

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/financiamiento_delete_confirm.html']
        return ['dashboard/financiamiento_delete_confirm.html']

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Reactivamos el lote antes de eliminar el financiamiento
        lote = self.object.lote
        lote.activo = True
        lote.save()

        # Eliminamos el objeto
        self.object.delete()
        
        if request.headers.get('HX-Request'):
            # Para HTMX, devolvemos la lista actualizada
            planes = Financiamiento.objects.all().order_by('id')
            return render(request, 'dashboard/partials/financiamientos_list_partial.html', 
                         {'planes': planes})
        else:
            # Para solicitudes normales, redirigimos
            return HttpResponseRedirect(self.get_success_url())

    # Sobrescribimos post para que use nuestro método delete personalizado
    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

class ClienteListView(ListView):
    model = Cliente
    paginate_by = 12
    context_object_name = 'clientes'

    def get_template_names(self):
        # Si HTMX, devolvemos solo el fragmento
        if self.request.headers.get('Hx-Request'):
            return ['dashboard/partials/cliente_list.html']
        # Si no, la vista completa
        return ['dashboard/clientes_list.html']
    
    def get_queryset(self):
        # ordena siempre por pk/ID ascendente
        return super().get_queryset().order_by('id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agregar contadores al contexto
        context['total_clientes'] = Cliente.objects.count()
        context['clientes_activos'] = Cliente.objects.count()  # Cambia esto si tienes un campo "activo"
        return context
    
class ClienteCreateView(CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'dashboard/cliente_form.html'

    def get_success_url(self):
        return reverse('dashboard:cliente_detail', kwargs={'pk': self.object.pk})

    def get_template_names(self):
        if self.request.headers.get('Hx-Request'):
            return ['dashboard/partials/cliente_form.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Añadimos una flag para indicar que es creación, no edición
        context['creating'] = True
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('Hx-Request'):
            return HttpResponse(
                status=200,
                headers={
                    'HX-Redirect': self.get_success_url()
                }
            )
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('Hx-Request'):
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

class ClienteDetailView(DetailView):
    model = Cliente
    context_object_name = 'cliente'
    
    def get_template_names(self):
        # Si es una solicitud HTMX, devolvemos un template parcial
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/cliente_detail.html']
        return ['dashboard/clientes_detail.html']

class ClienteUpdateView(UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'dashboard/cliente_form.html'

    def get_success_url(self):
        return reverse('dashboard:cliente_detail', kwargs={'pk': self.object.pk})

    def get_template_names(self):
        if self.request.headers.get('Hx-Request'):
            return ['dashboard/partials/cliente_form.html']
        return [self.template_name]

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('Hx-Request'):
            # Redirigir a la página de detalle después de una actualización exitosa
            return HttpResponse(
                status=200,
                headers={
                    'HX-Redirect': self.get_success_url()
                }
            )
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('Hx-Request'):
            # Devolver el formulario con errores para HTMX
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

    
class ClienteDeleteView(DeleteView):
    model = Cliente
    success_url = reverse_lazy('dashboard:cliente_list')

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/cliente_delete_confirm.html']
        return ['dashboard/cliente_delete_confirm.html']

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Eliminamos el objeto
        self.object.delete()
        
        if request.headers.get('HX-Request'):
            # Para HTMX, devolvemos la lista actualizada
            clientes = Cliente.objects.all().order_by('id')
            return render(request, 'dashboard/partials/cliente_list.html', 
                         {'clientes': clientes})
        else:
            # Para solicitudes normales, redirigimos
            return HttpResponseRedirect(self.get_success_url())

    # Sobrescribimos post para que use nuestro método delete personalizado
    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

class VendedorListView(ListView):
    """Listado de vendedores y apoderados."""
    model = Vendedor
    template_name = 'dashboard/vendedores_list.html'
    context_object_name = 'vendedores'
    paginate_by = 12
    ordering = ['id']           # ordenados por ID

    def get_template_names(self):
        if self.request.headers.get('HX-Request') == 'true':
            return ['dashboard/partials/vendedor_list.html']
        return ['dashboard/base.html']  # esta incluye el bloque content
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_vendedores'] = Vendedor.objects.count()
        ctx['vendedores_activos'] = Vendedor.objects.count()
        # para base.html, renderizará dentro del block content,
        # para partials solo se inyecta la lista:
        if self.request.headers.get('HX-Request') != 'true':
            ctx['inner_template'] = 'dashboard/partials/vendedor_list.html'
        return ctx

class VendedorUpdateView(UpdateView):
    model = Vendedor
    form_class = VendedorForm
    template_name = 'dashboard/vendedor_form.html'

    def get_success_url(self):
        return reverse('dashboard:vendedor_detail', kwargs={'pk': self.object.pk})

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/vendedor_form.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Añadir flag para indicar que es edición
        context['creating'] = False
        # Mostrar credenciales solo si el vendedor tiene usuario
        context['mostrar_credenciales'] = self.object.usuario is not None
        return context

    def form_valid(self, form):
        # Guardar el vendedor (y actualizar usuario a través del form)
        self.object = form.save()
        
        # Mensaje de éxito
        messages.success(self.request, f'Vendedor {self.object.nombre_completo} actualizado exitosamente.')
        
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                status=200,
                headers={
                    'HX-Redirect': self.get_success_url()
                }
            )
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('HX-Request'):
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

class VendedorCreateView(CreateView):
    model = Vendedor
    form_class = VendedorForm
    template_name = 'dashboard/vendedor_form.html'

    def get_success_url(self):
        return reverse('dashboard:vendedor_detail', kwargs={'pk': self.object.pk})

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/vendedor_form.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Añadimos una flag para indicar que es creación, no edición
        context['creating'] = True
        context['mostrar_credenciales'] = False
        return context

    def form_valid(self, form):
        # Guardar el vendedor primero (sin usuario aún)
        self.object = form.save(commit=False)
        self.object.save()
        form.save_m2m()  # Guardar relaciones ManyToMany

        # Asignar automáticamente todos los proyectos existentes
        todos_los_proyectos = Proyecto.objects.all()
        self.object.proyectos.set(todos_los_proyectos)
        
        # Crear usuario automáticamente y obtener las credenciales
        credenciales = crear_usuario_para_vendedor(self.object)
        
        # Mensaje de éxito con información del usuario creado
        messages.success(
            self.request, 
            f'Vendedor {self.object.nombre_completo} creado exitosamente. '
            f'Usuario: {credenciales["username"]}, '
            f'Contraseña: {credenciales["password"]}'
        )
        
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                status=200,
                headers={
                    'HX-Redirect': self.get_success_url()
                }
            )
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('HX-Request'):
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

class VendedorDetailView(DetailView):
    model = Vendedor
    context_object_name = 'vendedor'
    
    def get_template_names(self):
        # Si es una solicitud HTMX, devolvemos un template parcial
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/vendedor_detail.html']
        return ['dashboard/vendedores_detail.html']

class VendedorDeleteView(DeleteView):
    model = Vendedor
    success_url = reverse_lazy('dashboard:vendedor_list')

    def get_template_names(self):
        # Para HTMX devolvemos solo el formulario de confirmación parcial
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/vendedor_delete_confirm.html']
        return ['dashboard/vendedor_delete_confirm.html']

    def form_valid(self, form):
        # Guardar referencia al usuario antes de eliminar el vendedor
        usuario = self.object.usuario

        success_url = self.get_success_url()
        self.object.delete()

        # Eliminar el usuario asociado si existe
        if usuario:
            usuario.delete()
        
        if self.request.headers.get('HX-Request'):
            # Para solicitudes HTMX, devolvemos la lista actualizada de vendedores
            vendedores = Vendedor.objects.all().order_by('id')
            return render(self.request, 'dashboard/partials/vendedor_list.html', 
                         {'vendedores': vendedores})
        return redirect(success_url)

class PropietarioListView(ListView):
    model = Propietario
    paginate_by = 12
    context_object_name = 'propietarios'
    ordering = ['id']

    def get_template_names(self):
        if self.request.headers.get('Hx-Request'):
            return ['dashboard/partials/propietario_list_partial.html']
        return ['dashboard/propietarios_list.html']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_propietarios'] = Propietario.objects.count()
        return context

class PropietarioDetailView(DetailView):
    model = Propietario
    context_object_name = 'propietario'

    def get_template_names(self):
        if self.request.headers.get('Hx-Request'):
            return ['dashboard/partials/propietario_detail.html']
        return ['dashboard/propietarios_detail.html']

class PropietarioCreateView(CreateView):
    model = Propietario
    form_class = PropietarioForm
    template_name = 'dashboard/propietario_form.html'

    def get_success_url(self):
        return reverse('dashboard:propietario_detail', kwargs={'pk': self.object.pk})

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/propietario_form.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['creating'] = True
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                status=200,
                headers={
                    'HX-Redirect': self.get_success_url()
                }
            )
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('HX-Request'):
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

class PropietarioUpdateView(UpdateView):
    model = Propietario
    form_class = PropietarioForm
    template_name = 'dashboard/propietario_form.html'

    def get_success_url(self):
        return reverse('dashboard:propietario_detail', kwargs={'pk': self.object.pk})

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/propietario_form.html']
        return [self.template_name]

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                status=200,
                headers={
                    'HX-Redirect': self.get_success_url()
                }
            )
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('HX-Request'):
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

class PropietarioDeleteView(DeleteView):
    model = Propietario
    success_url = reverse_lazy('dashboard:propietario_list')

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/propietario_delete_confirm.html']
        return ['dashboard/propietario_delete_confirm.html']

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Eliminamos el objeto
        self.object.delete()
        
        if request.headers.get('HX-Request'):
            # Para solicitudes HTMX, devolvemos la lista actualizada de propietarios
            propietarios = Propietario.objects.all().order_by('id')
            return render(request, 'dashboard/partials/propietario_list_partial.html', 
                         {'propietarios': propietarios})
        else:
            # Para solicitudes normales, redirigimos
            return HttpResponseRedirect(self.get_success_url())

    # Sobrescribimos post para que use nuestro método delete personalizado
    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

class ProyectoListView(ListView):
    model = Proyecto
    template_name = 'dashboard/proyecto_list.html'            # vista completa
    context_object_name = 'proyectos'
    paginate_by = 12
    ordering = ['id']

    def get_queryset(self):
        return Proyecto.objects.all().order_by('id')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agregar contadores al contexto
        context['total_proyectos'] = Proyecto.objects.count()
        context['proyectos_activos'] = Proyecto.objects.count()  # Ajusta según tu modelo
        return context

    def get(self, request, *args, **kwargs):
        # Obtener el contexto usando get_context_data
        self.object_list = self.get_queryset()
        context = self.get_context_data()

        # Si es petición HTMX devolvemos solo el fragmento de la lista
        if request.headers.get('HX-Request'):
            return render(request, 'dashboard/partials/proyecto_list_partial.html', context)

        # Petición normal: plantilla completa que incluye el panel lateral
        return render(request, self.template_name, context)

class ProyectoDetailView(DetailView):
    model = Proyecto
    context_object_name = 'proyecto'

    def get_template_names(self):
        if self.request.headers.get('Hx-Request'):
            return ['dashboard/partials/proyecto_detail.html']
        return ['dashboard/proyectos_detail.html']
    
class ProyectoCreateView(CreateView):
    model = Proyecto
    form_class = ProyectoForm
    template_name = 'dashboard/proyecto_form.html'

    def get_success_url(self):
        return reverse('dashboard:proyecto_detail', kwargs={'pk': self.object.pk})

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/proyecto_form.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Añadimos una flag para indicar que es creación, no edición
        context['creating'] = True
        return context

    def form_valid(self, form):
        # Guardar el proyecto primero
        self.object = form.save(commit=False)
        self.object.save()
        form.save_m2m()  # Guardar relaciones ManyToMany si las hay
        
        # ✨ NUEVO: Asignar automáticamente a todos los vendedores activos
        vendedores_activos = Vendedor.objects.filter(activo=True)
        self.object.vendedores.set(vendedores_activos)
        
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                status=200,
                headers={
                    'HX-Redirect': self.get_success_url()
                }
            )
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('HX-Request'):
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

class ProyectoUpdateView(UpdateView):
    model = Proyecto
    form_class = ProyectoForm
    template_name = 'dashboard/proyecto_form.html'

    def get_success_url(self):
        return reverse('dashboard:proyecto_detail', kwargs={'pk': self.object.pk})

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/proyecto_form.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['creating'] = False
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                status=200,
                headers={
                    'HX-Redirect': self.get_success_url()
                }
            )
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('HX-Request'):
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

class ProyectoDeleteView(DeleteView):
    model = Proyecto
    success_url = reverse_lazy('dashboard:proyecto_list')

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/proyecto_confirm_delete.html']
        return ['dashboard/proyecto_confirm_delete.html']

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Eliminamos el objeto
        self.object.delete()
        
        if request.headers.get('HX-Request'):
            # Para solicitudes HTMX, devolvemos la lista actualizada de proyectos
            proyectos = Proyecto.objects.all().order_by('id')
            return render(request, 'dashboard/partials/proyecto_list_partial.html', 
                         {'proyectos': proyectos})
        else:
            # Para solicitudes normales, redirigimos
            return HttpResponseRedirect(self.get_success_url())

    # Sobrescribimos post para que use nuestro método delete personalizado
    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

class LoteListView(ListView):
    model = Lote
    template_name = "dashboard/lote_list.html"
    context_object_name = "lotes"
    paginate_by = 12
    ordering = ["id"]

    def get_queryset(self):
        qs = super().get_queryset().select_related("proyecto").order_by("id")
        proyecto_id = self.request.GET.get("proyecto")
        search = self.request.GET.get("search", "").strip()
        status = self.request.GET.get("status", "").strip().lower()

        if proyecto_id:
            qs = qs.filter(proyecto_id=proyecto_id)

        if status == "activo":
            qs = qs.filter(activo=True)
        elif status == "inactivo":
            qs = qs.filter(activo=False)

        if search:
            qs = qs.filter(
                Q(identificador__icontains=search) |
                Q(manzana__icontains=search) |
                Q(norte__icontains=search) |
                Q(sur__icontains=search) |
                Q(este__icontains=search) |
                Q(oeste__icontains=search) |
                Q(proyecto__nombre__icontains=search)
            )

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["proyectos"] = Proyecto.objects.all()
        ctx["proyecto_id"] = self.request.GET.get("proyecto", "")
        ctx["search"] = self.request.GET.get("search", "")
        ctx["status"] = self.request.GET.get("status", "")
        # Agregar contadores
        ctx["total_lotes"] = Lote.objects.count()
        ctx["lotes_activos"] = Lote.objects.filter(activo=True).count()
        ctx["lotes_inactivos"] = Lote.objects.filter(activo=False).count()
        return ctx

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/lote_list_partial.html']
        return [self.template_name]

class LoteDetailView(DetailView):
    model = Lote
    context_object_name = 'lote'

    def get_template_names(self):
        if self.request.headers.get('Hx-Request'):
            return ['dashboard/partials/lote_detail.html']
        return ['dashboard/lotes_detail.html']

class LoteCreateView(CreateView):
    model = Lote
    form_class = LoteForm
    template_name = 'dashboard/lote_form.html'

    def get_success_url(self):
        return reverse('dashboard:lote_detail', kwargs={'pk': self.object.pk})

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/lote_form.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Añadimos una flag para indicar que es creación, no edición
        context['creating'] = True
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                status=200,
                headers={
                    'HX-Redirect': self.get_success_url()
                }
            )
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('HX-Request'):
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

class LoteUpdateView(UpdateView):
    model = Lote
    form_class = LoteForm
    template_name = 'dashboard/lote_form.html'

    def get_success_url(self):
        return reverse('dashboard:lote_detail', kwargs={'pk': self.object.pk})

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/lote_form.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['creating'] = False
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                status=200,
                headers={
                    'HX-Redirect': self.get_success_url()
                }
            )
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('HX-Request'):
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

class LoteDeleteView(DeleteView):
    model = Lote
    success_url = reverse_lazy('dashboard:lote_list')

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/lote_confirm_delete.html']
        return ['dashboard/lote_confirm_delete.html']

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Eliminamos el objeto
        self.object.delete()
        
        if request.headers.get('HX-Request'):
            # Para solicitudes HTMX, devolvemos la lista actualizada de lotes
            lotes = Lote.objects.all().order_by('id')
            return render(request, 'dashboard/partials/lote_list_partial.html', 
                         {'lotes': lotes})
        else:
            # Para solicitudes normales, redirigimos
            return HttpResponseRedirect(self.get_success_url())

    # Sobrescribimos post para que use nuestro método delete personalizado
    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)
        
# === VISTAS PARA BENEFICIARIOS ===
class BeneficiarioListView(ListView):
    model = Beneficiario
    paginate_by = 12
    context_object_name = 'beneficiarios'
    ordering = ['id']

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/beneficiario_list_partial.html']
        return ['dashboard/beneficiario_list.html']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_beneficiarios'] = Beneficiario.objects.count()
        return context

class BeneficiarioDetailView(DetailView):
    model = Beneficiario
    context_object_name = 'beneficiario'

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/beneficiario_detail_partial.html']
        return ['dashboard/beneficiario_detail.html']

class BeneficiarioCreateView(CreateView):
    model = Beneficiario
    form_class = BeneficiarioForm
    template_name = 'dashboard/beneficiario_form.html'

    def get_success_url(self):
        return reverse('dashboard:beneficiario_detail', kwargs={'pk': self.object.pk})

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/beneficiario_form_partial.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['creating'] = True
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                status=200,
                headers={
                    'HX-Redirect': self.get_success_url()
                }
            )
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('HX-Request'):
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

class BeneficiarioUpdateView(UpdateView):
    model = Beneficiario
    form_class = BeneficiarioForm
    template_name = 'dashboard/beneficiario_form.html'

    def get_success_url(self):
        return reverse('dashboard:beneficiario_detail', kwargs={'pk': self.object.pk})

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/beneficiario_form_partial.html']
        return [self.template_name]

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                status=200,
                headers={
                    'HX-Redirect': self.get_success_url()
                }
            )
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('HX-Request'):
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

class BeneficiarioDeleteView(DeleteView):
    model = Beneficiario
    success_url = reverse_lazy('dashboard:beneficiario_list')

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/beneficiario_delete_confirm_partial.html']
        return ['dashboard/beneficiario_confirm_delete.html']

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        
        if request.headers.get('HX-Request'):
            beneficiarios = Beneficiario.objects.all().order_by('id')
            return render(request, 'dashboard/partials/beneficiario_list_partial.html', 
                         {'beneficiarios': beneficiarios})
        else:
            return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

# === VISTAS PARA CARTA INTENCIÓN ===
class CartaIntencionListView(ListView):
    model = CartaIntencion
    paginate_by = 12
    context_object_name = 'cartas_intencion'
    ordering = ['-creado_en']  # Más recientes primero

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/cartaintencion_list_partial.html']
        return ['dashboard/cartaintencion_list.html']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_cartas_intencion'] = CartaIntencion.objects.count()
        context['cartas_activas'] = CartaIntencion.objects.count()  # Puedes ajustar si tienes campo activo
        
        # Filtros y búsqueda (similar a Trámites)
        usuario_id = self.request.GET.get('usuario')
        search_term = self.request.GET.get('search')
        
        context['filtro_usuario_actual'] = usuario_id
        context['termino_busqueda_actual'] = search_term
        
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Optimizar consultas relacionadas
        queryset = queryset.select_related(
            'financiamiento',
            'financiamiento__lote',
            'financiamiento__lote__proyecto',
            'vendedor'
        )
        
        # Aplicar filtros
        #search_term = self.request.GET.get('search')
        #if search_term:
        #    queryset = queryset.filter(
        #        models.Q(nombre_cliente__icontains=search_term) |
        #        models.Q(financiamiento__lote__identificador__icontains=search_term) |
        #        models.Q(numero_id__icontains=search_term)
        #    )
        
        return queryset

class CartaIntencionDetailView(DetailView):
    model = CartaIntencion
    context_object_name = 'carta'

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/cartaintencion_detail_partial.html']
        return ['dashboard/cartaintencion_detail.html']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'financiamiento',
            'financiamiento__lote',
            'financiamiento__lote__proyecto',
            'vendedor'
        )

class CartaIntencionCreateView(CreateView):
    model = CartaIntencion
    form_class = CartaIntencionForm
    template_name = 'dashboard/cartaintencion_form.html'

    def get_success_url(self):
        return reverse('dashboard:cartaintencion_detail', kwargs={'pk': self.object.pk})

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/cartaintencion_form_partial.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['creating'] = True
        
        # Pasar financiamiento_id si viene en GET
        financiamiento_id = self.request.GET.get('financiamiento_id')
        if financiamiento_id:
            context['financiamiento_id'] = financiamiento_id
            
        return context

    def get_initial(self):
        initial = super().get_initial()
        financiamiento_id = self.request.GET.get('financiamiento_id')
        if financiamiento_id:
            try:
                financiamiento = Financiamiento.objects.get(pk=financiamiento_id)
                initial['financiamiento'] = financiamiento
                initial['nombre_cliente'] = financiamiento.nombre_cliente
                initial['oferta'] = financiamiento.precio_lote
            except Financiamiento.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                status=200,
                headers={
                    'HX-Redirect': self.get_success_url()
                }
            )
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('HX-Request'):
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

class CartaIntencionUpdateView(UpdateView):
    model = CartaIntencion
    form_class = CartaIntencionForm
    template_name = 'dashboard/cartaintencion_form.html'

    def get_success_url(self):
        return reverse('dashboard:cartaintencion_detail', kwargs={'pk': self.object.pk})

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/cartaintencion_form_partial.html']
        return [self.template_name]

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                status=200,
                headers={
                    'HX-Redirect': self.get_success_url()
                }
            )
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.headers.get('HX-Request'):
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400
            )
        return response

class CartaIntencionDeleteView(DeleteView):
    model = CartaIntencion
    success_url = reverse_lazy('dashboard:cartaintencion_list')

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/partials/cartaintencion_delete_confirm_partial.html']
        return ['dashboard/cartaintencion_confirm_delete.html']

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        
        if request.headers.get('HX-Request'):
            cartas = CartaIntencion.objects.all().order_by('-creado_en')
            return render(request, 'dashboard/partials/cartaintencion_list_partial.html', 
                         {'cartas_intencion': cartas})
        else:
            return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

class CartaIntencionDownloadView(DetailView):
    """
    Vista para descargar cartas de intención en PDF o Word.
    Reutiliza la función build_carta_intencion_from_instance de financiamiento.
    """
    model = CartaIntencion

    def get(self, request, *args, **kwargs):
        carta = self.get_object()
        formato = self.kwargs.get('formato', 'pdf')

        if formato == 'pdf':
            return self.generar_pdf(carta)
        elif formato == 'word':
            return self.generar_word(carta)
        else:
            return HttpResponse("Formato no soportado", status=400)

    def generar_pdf(self, carta):
        """
        Genera y devuelve un PDF de la carta de intención.
        Reutiliza la lógica existente en financiamiento/views.py
        """
        # Ruta a la plantilla de carta de intención
        tpl_path = os.path.join(settings.BASE_DIR, 'pdfs/templates/pdfs/carta_intencion_template.docx')
        
        # Verificar que la plantilla existe
        if not os.path.exists(tpl_path):
            return HttpResponse("Plantilla no encontrada", status=500)
        
        try:
            # Cargar plantilla
            tpl = DocxTemplate(tpl_path)
            
            # Generar contexto usando la función existente
            context = build_carta_intencion_from_instance(carta, request=self.request, tpl=tpl)
            
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

    def generar_word(self, carta):
        """
        Genera y devuelve un documento Word de la carta de intención.
        """
        # Ruta a la plantilla de carta de intención
        tpl_path = os.path.join(settings.BASE_DIR, 'pdfs/templates/pdfs/carta_intencion_template.docx')
        
        # Verificar que la plantilla existe
        if not os.path.exists(tpl_path):
            return HttpResponse("Plantilla no encontrada", status=500)
        
        try:
            # Cargar plantilla
            tpl = DocxTemplate(tpl_path)
            
            # Generar contexto usando la función existente
            context = build_carta_intencion_from_instance(carta, request=self.request, tpl=tpl)
            
            # Renderizar plantilla
            tpl.render(context)
            
            # Crear un buffer en memoria para el documento
            output = io.BytesIO()
            tpl.save(output)
            output.seek(0)
            
            # Configurar respuesta
            filename = f"carta_intencion_{carta.nombre_cliente.replace(' ', '_')}_{carta.id}.docx"
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
        
        except Exception as e:
            return HttpResponse(f"Error al generar el documento: {str(e)}", status=500)

def home(request):
    ctx = {
      'num_clientes': Cliente.objects.count(),
      'num_proyectos': Proyecto.objects.count(),
      'num_vendedores': Vendedor.objects.count(),
      'num_propietarios': Propietario.objects.count(),
      'num_lotes': Lote.objects.count(),
      'num_financiamientos': Financiamiento.objects.count(),
      'num_tramites': Tramite.objects.count(),
      'num_beneficiarios': Beneficiario.objects.count(),
      'num_cartas_intencion': CartaIntencion.objects.count(),
      # Nuevos contadores para Commeta
        'num_configuraciones_commeta': ConfiguracionCommeta.objects.count(),
        'num_financiamientos_commeta': FinanciamientoCommeta.objects.count(),
    }
    # Si es petición HTMX, devolvemos _solo_ el partial
    if request.headers.get('HX-Request'):
        return render(request,
                      'dashboard/partials/home_content.html',
                      ctx)
    # Petición normal -> página completa
    return render(request,
                  'dashboard/home.html',
                  ctx)

import time
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def health_check(request):
    """Endpoint simple para health checks - mantener activa la app"""
    return JsonResponse({
        "status": "ok", 
        "timestamp": time.time(),
        "message": "Application is alive",
        "app": "dashboard"
    })




