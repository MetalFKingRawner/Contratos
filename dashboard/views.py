# dashboard/views.py
from django.views.generic import View
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from workflow.models import Tramite  # Ajusta al path real de tu modelo
from financiamiento.models import Financiamiento  # Ajusta import según tu estructura
from core.models import Cliente  # o donde tengas definido Cliente
from core.models import Vendedor, Propietario
from core.models import Proyecto, Lote
from django.db.models import Prefetch
from core.forms import ClienteForm, VendedorForm  # lo definimos a continuación
from django.urls import reverse_lazy
from django.views.generic import UpdateView
from django.shortcuts import render
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest, HttpResponseRedirect, JsonResponse, HttpResponse
from django.urls import reverse
from .forms import PropietarioForm, ProyectoForm,LoteForm, TramiteForm
from django.db.models import Q
from financiamiento.forms import FinanciamientoForm
#class DashboardHomeView(TemplateView):
#    template_name = 'dashboard/home.html'

import os
import io
from workflow.docs import DOCUMENTOS
from pdfs.utils import convert_docx_to_pdf 
from docxtpl import DocxTemplate
from django.conf import settings


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
        
        # Intentar pasar el segundo cliente si el builder lo soporta
        try:
            context = builder(
                fin, cli, ven, 
                request=request, 
                tpl=tpl, 
                firma_data=tramite.firma_cliente, 
                clausulas_adicionales=clausulas_adicionales,
                cliente2=cli2
            )
        except TypeError as e:
            # Si el builder no acepta cliente2, intentar sin él
            try:
                context = builder(
                    fin, cli, ven, 
                    request=request, 
                    tpl=tpl, 
                    firma_data=tramite.firma_cliente, 
                    clausulas_adicionales=clausulas_adicionales
                )
            except TypeError:
                # Versión mínima
                context = builder(fin, cli, ven)
        
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
            response['Content-Disposition'] = f'attachment; filename="{document_type}.docx"'
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
                response = HttpResponse(pdf_data, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{document_type}.pdf"'
                return response
            else:
                return HttpResponse("Error al generar PDF", status=500)
        
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
        # Agregar contadores al contexto
        context['total_tramites'] = Tramite.objects.count()
        context['tramites_activos'] = Tramite.objects.count()  # Cambia esto si tienes un campo "activo"
        return context

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
        # Guardar el formulario (que incluye las cláusulas)
        self.object = form.save()
        
        if self.request.headers.get('HX-Request'):
            # Devolver el detalle actualizado para HTMX
            return render(self.request, 'dashboard/partials/tramites_detail_partial.html', 
                         {'tramite': self.object})
        return redirect('dashboard:tramite_detail', pk=self.object.pk)

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
        response = super().delete(request, *args, **kwargs)
        if request.headers.get('HX-Request'):
            return TramiteListView.as_view()(request._request)
        return response

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
        response = super().form_valid(form)
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
        success_url = self.get_success_url()
        self.object.delete()
        
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

def home(request):
    ctx = {
      'num_clientes': Cliente.objects.count(),
      'num_proyectos': Proyecto.objects.count(),
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





