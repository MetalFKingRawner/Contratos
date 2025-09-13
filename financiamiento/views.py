from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from .models import Financiamiento
from .forms import FinanciamientoForm

class FinanciamientoListView(ListView):
    model = Financiamiento
    template_name = "financiamiento/list.html"
    context_object_name = "planes"

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
        
        # Cambiamos su estado a inactivo
        lote.activo = False
        lote.save()
        
        return response

class FinanciamientoUpdateView(UpdateView):
    model = Financiamiento
    form_class = FinanciamientoForm
    template_name = "financiamiento/form.html"
    success_url = reverse_lazy('financiamiento:list')

