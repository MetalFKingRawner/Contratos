from django.urls import path
from .views import (
    FinanciamientoListView, 
    FinanciamientoCreateView, 
    FinanciamientoUpdateView,
    CartaIntencionListView,   # Nueva vista para listar cartas de intención
    CartaIntencionCreateView, # Nueva vista para crear cartas de intención
    CartaIntencionUpdateView, # Nueva vista para editar cartas de intención
    descargar_carta_intencion_pdf, # Vista para generar PDF
    financiamiento_ajax_data
)

app_name = 'financiamiento'

urlpatterns = [
    path('',       FinanciamientoListView.as_view(),   name='list'),
    path('nuevo/', FinanciamientoCreateView.as_view(), name='create'),
    path('<int:pk>/editar/', FinanciamientoUpdateView.as_view(), name='edit'),
    # URLs para Cartas de Intención
    path('cartas-intencion/', CartaIntencionListView.as_view(), name='carta_intencion_list'),
    path('cartas-intencion/nueva/', CartaIntencionCreateView.as_view(), name='carta_intencion_create'),
    path('cartas-intencion/<int:pk>/editar/', CartaIntencionUpdateView.as_view(), name='carta_intencion_edit'),
    path('cartas-intencion/<int:pk>/descargar-pdf/', descargar_carta_intencion_pdf, name='carta_intencion_descargar_pdf'),
    # URL para AJAX
    path('ajax/financiamiento/<int:pk>/', financiamiento_ajax_data, name='financiamiento_ajax_data'),
]

