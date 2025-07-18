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
        # 1) Guardamos el financiamiento y obtenemos la instancia:
        response = super().form_valid(form)  
        financ = self.object  # instancia recién creada

        # 2) Desactivamos el lote asociado:
        lote = financ.lote
        lote.activo = False
        lote.save()

        # 3) Devolvemos la respuesta normal:
        return response

class FinanciamientoUpdateView(UpdateView):
    model = Financiamiento
    form_class = FinanciamientoForm
    template_name = "financiamiento/form.html"
    success_url = reverse_lazy('financiamiento:list')
