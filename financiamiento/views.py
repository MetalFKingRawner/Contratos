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

class FinanciamientoUpdateView(UpdateView):
    model = Financiamiento
    form_class = FinanciamientoForm
    template_name = "financiamiento/form.html"
    success_url = reverse_lazy('financiamiento:list')
