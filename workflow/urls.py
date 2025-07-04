from django.views.generic import TemplateView
from django.urls import path
from . import views
from .views import obtener_datos_financiamiento
from .views import GenerarCartaIntencionView, Paso1FinanciamientoView, ClienteDataView, SeleccionVendedorView, AvisoPrivacidadView, SeleccionDocumentosView

from .views import (
    SeleccionDocumentoView,
    SolicitudContratoView,
    # ... otras vistas
)

app_name = "workflow"

urlpatterns = [
    path('carta/aviso/', views.AvancePruebaView.as_view(), name='aviso_carta'),
    path('contrato/aviso/', views.AvancePruebaView.as_view(), name='aviso_contrato'),
    path('solicitud/', SolicitudContratoView.as_view(), name='solicitud'),
    path('ajax/financiamiento/', obtener_datos_financiamiento, name='ajax_financiamiento'),
    path('generar-carta/', GenerarCartaIntencionView.as_view(), name='generar_carta'),
     path('inicio/', Paso1FinanciamientoView.as_view(), name='paso1_financiamiento'),
    path('cliente/', ClienteDataView.as_view(), name='paso2_cliente'),
    path('vendedor/', SeleccionVendedorView.as_view(), name='paso_vendedor'),
    path('aviso-privacidad/', AvisoPrivacidadView.as_view(), name='aviso_privacidad'),
    path('documentos/', SeleccionDocumentosView.as_view(), name='paso3_documentos'),
    # reemplaza AvancePruebaView por la vista real cuando la crees
]

class SeleccionDocumentoView(TemplateView):
    template_name = "inicio.html"