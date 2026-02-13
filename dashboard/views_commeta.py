from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from core.models import ConfiguracionCommeta, Lote, Proyecto
from financiamiento.models import FinanciamientoCommeta
from financiamiento.forms import FinanciamientoCommetaForm
from django.http import HttpResponse, HttpResponseRedirect
from .forms import ConfiguracionCommetaForm


import logging

logger = logging.getLogger(__name__)

# Luego en cada método importante, puedes usar:
logger.debug(f"Mensaje de debug")
logger.info(f"Mensaje informativo")
# ========== CONFIGURACIONES COMMETA ==========

class ConfiguracionCommetaListView(ListView):
    """Listado de configuraciones Commeta."""
    model = ConfiguracionCommeta
    context_object_name = 'configuraciones'
    paginate_by = 20

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/commeta/partials/configuracion_list_partial.html']
        return ['dashboard/commeta/configuracion_list.html']

    def get_queryset(self):
        queryset = ConfiguracionCommeta.objects.select_related('lote', 'lote__proyecto')
        
        # Filtrar por zona si se especifica
        zona = self.request.GET.get('zona')
        if zona:
            queryset = queryset.filter(zona=zona)
        
        # Filtrar por tipo de esquema si se especifica
        tipo_esquema = self.request.GET.get('tipo_esquema')
        if tipo_esquema:
            queryset = queryset.filter(tipo_esquema=tipo_esquema)
        
        # Filtrar solo activos si se solicita
        activo = self.request.GET.get('activo')
        if activo == 'true':
            queryset = queryset.filter(activo=True)
        elif activo == 'false':
            queryset = queryset.filter(activo=False)
        
        return queryset.order_by('zona', 'lote__identificador')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_configuraciones'] = ConfiguracionCommeta.objects.count()
        context['configuraciones_activas'] = ConfiguracionCommeta.objects.filter(activo=True).count()
        context['zonas'] = ConfiguracionCommeta.ZONA_CHOICES
        context['tipos_esquema'] = ConfiguracionCommeta.TIPO_ESQUEMA_CHOICES
        
        # Estadísticas por zona
        zonas_stats = {}
        for zona_code, zona_name in ConfiguracionCommeta.ZONA_CHOICES:
            count = ConfiguracionCommeta.objects.filter(zona=zona_code).count()
            zonas_stats[zona_code] = {
                'nombre': zona_name,
                'count': count
            }
        context['zonas_stats'] = zonas_stats
        
        return context

class ConfiguracionCommetaDetailView(DetailView):
    model = ConfiguracionCommeta
    template_name = 'dashboard/commeta/partials/configuracion_detail.html'
    context_object_name = 'configuracion'

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return 'dashboard/commeta/partials/configuracion_detail.html'
        return 'dashboard/commeta/configuracion_detail.html'

class ConfiguracionCommetaCreateView(CreateView):
    model = ConfiguracionCommeta
    form_class = ConfiguracionCommetaForm
    template_name = 'dashboard/commeta/partials/configuracion_form.html'

    def get_success_url(self):
        return reverse_lazy('commeta:commeta_configuracion_list')

    def form_valid(self, form):
        self.object = form.save()
        
        if self.request.headers.get('HX-Request'):
            # Devolver el detalle de la configuración recién creada
            return render(
                self.request, 
                'dashboard/commeta/partials/configuracion_detail.html', 
                {'configuracion': self.object}
            )
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        if self.request.headers.get('HX-Request'):
            # Re-renderizar el formulario con errores
            context = self.get_context_data(form=form)
            return render(
                self.request,
                self.template_name,
                context
            )
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'create'
        context['zonas'] = ConfiguracionCommeta.ZONA_CHOICES
        context['tipos_esquema'] = ConfiguracionCommeta.TIPO_ESQUEMA_CHOICES
        return context


class ConfiguracionCommetaUpdateView(UpdateView):
    model = ConfiguracionCommeta
    form_class = ConfiguracionCommetaForm
    template_name = 'dashboard/commeta/partials/configuracion_form.html'

    def get_success_url(self):
        return reverse_lazy('commeta:commeta_configuracion_list')

    def form_valid(self, form):
        self.object = form.save()
        
        if self.request.headers.get('HX-Request'):
            # Devolver el detalle actualizado
            return render(
                self.request, 
                'dashboard/commeta/partials/configuracion_detail.html', 
                {'configuracion': self.object}
            )
        return HttpResponseRedirect(self.get_success_url())
    

    def form_invalid(self, form):
        if self.request.headers.get('HX-Request'):
            # Re-renderizar el formulario con errores
            context = self.get_context_data(form=form)
            return render(
                self.request,
                self.template_name,
                context
            )
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'edit'
        context['zonas'] = ConfiguracionCommeta.ZONA_CHOICES
        context['tipos_esquema'] = ConfiguracionCommeta.TIPO_ESQUEMA_CHOICES
        context['tipo_esquema_actual'] = self.object.tipo_esquema
        return context

class ConfiguracionCommetaDeleteView(DeleteView):
    model = ConfiguracionCommeta
    success_url = reverse_lazy('commeta:commeta_configuracion_list')

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/commeta/partials/configuracion_delete_confirm.html']
        return ['dashboard/commeta/configuracion_delete_confirm.html']

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if request.headers.get('HX-Request'):
            configuraciones = ConfiguracionCommeta.objects.select_related('lote').order_by('zona', 'lote__identificador')
            return render(request, 'dashboard/commeta/partials/configuracion_list_partial.html', 
                         {'configuraciones': configuraciones})
        else:
            return HttpResponseRedirect(self.get_success_url())

# ========== FINANCIAMIENTOS COMMETA ==========

class FinanciamientoCommetaListView(ListView):
    """Listado de financiamientos Commeta."""
    model = FinanciamientoCommeta
    context_object_name = 'planes'
    paginate_by = 12  # Puedes ajustar este número

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/commeta/partials/financiamiento_list_partial.html']
        return ['dashboard/commeta/financiamiento_list.html']

    def get_queryset(self):
        return FinanciamientoCommeta.objects.select_related(
            'financiamiento',
            'financiamiento__lote',
            'financiamiento__lote__proyecto',
            'configuracion_original'
        ).order_by('-financiamiento__creado_en')  # Ordenar por fecha de creación descendente

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_financiamientos'] = FinanciamientoCommeta.objects.count()
        return context

class FinanciamientoCommetaDetailView(DetailView):
    model = FinanciamientoCommeta
    template_name = 'dashboard/commeta/partials/financiamiento_detail.html'
    context_object_name = 'plan'

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return 'dashboard/commeta/partials/financiamiento_detail.html'
        return 'dashboard/commeta/financiamiento_detail.html'

class FinanciamientoCommetaCreateView(CreateView):
    model = FinanciamientoCommeta
    form_class = FinanciamientoCommetaForm
    template_name = 'dashboard/commeta/partials/financiamiento_form.html'

    def get_form_kwargs(self):
        """Auto-detectar proyecto Commeta si no viene en URL"""
        kwargs = super().get_form_kwargs()
        
        # Intentar obtener proyecto Commeta de la URL
        proyecto_commeta_id = self.request.GET.get('proyecto_commeta')
        
        if proyecto_commeta_id:
            # Si viene en URL, usarlo
            try:
                proyecto = Proyecto.objects.get(id=proyecto_commeta_id, tipo_proyecto='commeta')
                kwargs['proyecto_commeta'] = proyecto
            except Proyecto.DoesNotExist:
                pass
        else:
            # Si no viene en URL, buscar automáticamente proyectos Commeta
            proyectos_commeta = Proyecto.objects.filter(tipo_proyecto='commeta')
            
            if proyectos_commeta.exists():
                # Tomar el primer proyecto Commeta (puedes ajustar la lógica si hay más de uno)
                kwargs['proyecto_commeta'] = proyectos_commeta.first()
                print(f"✅ Proyecto Commeta auto-detectado: {proyectos_commeta.first().nombre}")
            else:
                print("⚠️ No se encontraron proyectos Commeta")
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'create'
        
        # Determinar el proyecto Commeta para el contexto
        proyecto_commeta = None
        
        # 1. Intentar obtener del formulario kwargs
        form_kwargs = self.get_form_kwargs()
        if 'proyecto_commeta' in form_kwargs:
            proyecto_commeta = form_kwargs['proyecto_commeta']
        
        # 2. Si no está en kwargs, buscar directamente
        if not proyecto_commeta:
            proyectos_commeta = Proyecto.objects.filter(tipo_proyecto='commeta')
            if proyectos_commeta.exists():
                proyecto_commeta = proyectos_commeta.first()
        
        if proyecto_commeta:
            context['proyecto_commeta'] = proyecto_commeta
            # Filtrar lotes solo de este proyecto Commeta
            context['lotes_commeta'] = Lote.objects.filter(
                proyecto=proyecto_commeta, 
                activo=True
            )
            print(f"📊 Lotes Commeta disponibles: {context['lotes_commeta'].count()}")
        
        # Para edición, indicar que NO es edición (es creación)
        context['es_edicion'] = False
        
        return context

    def form_valid(self, form):
        """Guardar el financiamiento Commeta"""
        # Guardar el financiamiento base (se guarda automáticamente por el formulario)
        response = super().form_valid(form)
        
        # Desactivar el lote
        lote = form.cleaned_data['lote']
        lote.activo = False
        lote.save()
        
        print(f"✅ Financiamiento Commeta creado: ID {self.object.id}")
        print(f"   Lote {lote.identificador} marcado como inactivo")
        
        if self.request.headers.get('HX-Request'):
            # Devolver la lista actualizada
            return render(self.request, 'dashboard/commeta/partials/financiamiento_list_partial.html', 
                         {'planes': FinanciamientoCommeta.objects.all().order_by('id')})
        return response

    def get_success_url(self):
        return reverse_lazy('commeta:commeta_financiamiento_list')
    
class FinanciamientoCommetaUpdateView(UpdateView):
    model = FinanciamientoCommeta
    form_class = FinanciamientoCommetaForm
    template_name = 'dashboard/commeta/partials/financiamiento_form.html'

    def get_form_kwargs(self):
        """En edición, pasar el proyecto del financiamiento existente"""
        kwargs = super().get_form_kwargs()
        
        # En edición, obtener el proyecto del financiamiento existente
        if self.object and hasattr(self.object, 'financiamiento'):
            lote = self.object.financiamiento.lote
            if lote and hasattr(lote, 'proyecto') and lote.proyecto.tipo_proyecto == 'commeta':
                kwargs['proyecto_commeta'] = lote.proyecto
                print(f"✅ Proyecto Commeta pasado al formulario: {lote.proyecto.nombre}")
        
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'edit'
        context['object'] = self.object
        context['es_edicion'] = True
        
        # Cargar proyecto Commeta
        if self.object and hasattr(self.object, 'financiamiento'):
            lote = self.object.financiamiento.lote
            if lote and hasattr(lote, 'proyecto') and lote.proyecto.tipo_proyecto == 'commeta':
                context['proyecto_commeta'] = lote.proyecto
                context['lotes_commeta'] = lote.proyecto.lotes.all()  # Mostrar todos los lotes
        
        # Pasar el valor actual de tipo_esquema al contexto
        if self.object:
            context['tipo_esquema_actual'] = self.object.tipo_esquema
            print(f"✅ Tipo esquema actual: {self.object.tipo_esquema}")
        
        return context

    def form_valid(self, form):
        print(f"🔄 Iniciando actualización de FinanciamientoCommeta ID {self.object.id}")

        financiamiento_commeta_id = self.object.pk
        
        # Obtener lote anterior y nuevo
        lote_anterior = self.object.financiamiento.lote
        lote_nuevo = form.cleaned_data['lote']
        
        print(f"📊 Comparando lotes: {lote_anterior.identificador} -> {lote_nuevo.identificador}")
        
        # Guardar el formulario (esto actualizará el Financiamiento y el FinanciamientoCommeta)
        response = super().form_valid(form)
        
        # Si cambió de lote, activar el anterior y desactivar el nuevo
        if lote_anterior.pk != lote_nuevo.pk:
            lote_anterior.activo = True
            lote_anterior.save()
            lote_nuevo.activo = False
            lote_nuevo.save()
            print(f"🔄 Cambio de lote completado: {lote_anterior.identificador} activado, {lote_nuevo.identificador} desactivado")
        else:
            lote_nuevo.activo = False
            lote_nuevo.save()
            print(f"✅ Mismo lote mantenido: {lote_nuevo.identificador} desactivado")

        if self.request.headers.get('HX-Request'):
            print(f"✅ HTMX: Devolviendo detalle actualizado")
            
            # 🔥 SOLUCIÓN: Recargar el objeto con todas las relaciones
            # Esto asegura que todas las relaciones estén disponibles en el template
            plan_actualizado = FinanciamientoCommeta.objects.select_related(
                'financiamiento',
                'financiamiento__lote',
                'financiamiento__lote__proyecto',
                'configuracion_original'
            ).get(pk=financiamiento_commeta_id)
            
            print(f"🔍 Objeto recargado con relaciones:")
            print(f"   - ID: {plan_actualizado.id}")
            print(f"   - Financiamiento: {plan_actualizado.financiamiento.id}")
            print(f"   - Cliente: {plan_actualizado.financiamiento.nombre_cliente}")
            print(f"   - Lote: {plan_actualizado.financiamiento.lote.identificador}")
            print(f"   - Proyecto: {plan_actualizado.financiamiento.lote.proyecto.nombre}")
            
            return render(
                self.request, 
                'dashboard/commeta/partials/financiamiento_detail.html', 
                {'plan': plan_actualizado}
            )
        
        print(f"✅ Actualización completada para FinanciamientoCommeta ID {self.object.id}")
        return response

    def get_success_url(self):
        return reverse_lazy('commeta:commeta_financiamiento_detail', kwargs={'pk': self.object.pk})

    

class FinanciamientoCommetaDeleteView(DeleteView):
    model = FinanciamientoCommeta
    success_url = reverse_lazy('commeta:commeta_financiamiento_list')

    def get_template_names(self):
        if self.request.headers.get('HX-Request'):
            return ['dashboard/commeta/partials/financiamiento_delete_confirm.html']
        return ['dashboard/commeta/financiamiento_delete_confirm.html']

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        financiamiento = self.object.financiamiento
        lote = financiamiento.lote
        
        print(f"🗑️ Eliminando financiamiento Commeta ID: {self.object.id}")
        print(f"   Cliente: {financiamiento.nombre_cliente}")
        print(f"   Lote: {lote.identificador}")
        
        # Reactivamos el lote antes de eliminar el financiamiento
        lote.activo = True
        lote.save()
        print(f"✅ Lote {lote.identificador} reactivado")

        # Guardar datos para mensaje de éxito
        cliente_nombre = financiamiento.nombre_cliente
        lote_identificador = lote.identificador
        
        # Eliminamos el objeto FinanciamientoCommeta
        self.object.delete()
        
        # También eliminamos el objeto Financiamiento asociado
        financiamiento.delete()
        print(f"✅ Financiamiento y detalle Commeta eliminados")

        if request.headers.get('HX-Request'):
            # Para HTMX, devolvemos la lista actualizada
            planes = FinanciamientoCommeta.objects.all().order_by('id')
            return render(request, 'dashboard/commeta/partials/financiamiento_list_partial.html', 
                         {'planes': planes})
        else:
            return HttpResponseRedirect(self.get_success_url())

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Asegurarnos de que el objeto esté disponible en el template
        context['object'] = self.object
        return context