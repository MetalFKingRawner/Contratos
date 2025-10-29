# dashboard/urls.py
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('tramites/', views.TramiteListView.as_view(), name='tramite_list'),
    path('tramites/<int:pk>/', views.TramiteDetailView.as_view(), name='tramite_detail'),
    path('tramites/create/', views.TramiteCreateView.as_view(), name='tramite_create'),
    path('tramites/<int:pk>/edit/', views.TramiteUpdateView.as_view(), name='tramite_update'),
    path('tramites/<int:pk>/delete/', views.TramiteDeleteView.as_view(), name='tramite_delete'),
    # Nueva URL para descarga de documentos (temporal)
    path('tramites/<int:pk>/download/<str:document_type>/<str:format>/', views.DownloadDocumentView.as_view(), name='download_document'),
    # —— Nuevo módulo Financiamientos —— 
    path('financiamientos/', views.FinanciamientoListView.as_view(), name='financiamiento_list'),
    path('financiamientos/<int:pk>/', views.FinanciamientoDetailView.as_view(), name='financiamiento_detail'),
    path('financiamientos/create/', views.FinanciamientoCreateView.as_view(), name='financiamiento_create'),
    path('financiamientos/<int:pk>/edit/', views.FinanciamientoUpdateView.as_view(), name='financiamiento_update'),
    path('financiamientos/<int:pk>/delete/', views.FinanciamientoDeleteView.as_view(), name='financiamiento_delete'),
    path('clientes/', views.ClienteListView.as_view(), name='cliente_list'),
    path('clientes/<int:pk>/', views.ClienteDetailView.as_view(), name='cliente_detail'),
    path('clientes/<int:pk>/edit/', views.ClienteUpdateView.as_view(), name='cliente_update'),
    path('clientes/create/', views.ClienteCreateView.as_view(), name='cliente_create'),
    path('clientes/<int:pk>/delete/', views.ClienteDeleteView.as_view(), name='cliente_delete'),
    # Vendedores
    path('vendedores/', views.VendedorListView.as_view(), name='vendedor_list'),
    path('vendedores/<int:pk>/', views.VendedorDetailView.as_view(), name='vendedor_detail'),
    path('vendedores/<int:pk>/edit/', views.VendedorUpdateView.as_view(), name='vendedor_update'),
    path('vendedores/<int:pk>/delete/', views.VendedorDeleteView.as_view(), name='vendedor_delete'),
    path('vendedores/create/', views.VendedorCreateView.as_view(), name='vendedor_create'),
    
    # Propietarios
    path('propietarios/', views.PropietarioListView.as_view(), name='propietario_list'),
    path('propietarios/create/', views.PropietarioCreateView.as_view(), name='propietario_create'),
    path('propietarios/<int:pk>/', views.PropietarioDetailView.as_view(), name='propietario_detail'),
    path('propietarios/<int:pk>/edit/', views.PropietarioUpdateView.as_view(), name='propietario_update'),
    path('propietarios/<int:pk>/delete/', views.PropietarioDeleteView.as_view(), name='propietario_delete'),

    # Proyectos
    path('proyectos/', views.ProyectoListView.as_view(), name='proyecto_list'),
    path('proyectos/create/', views.ProyectoCreateView.as_view(), name='proyecto_create'),
    path('proyectos/<int:pk>/', views.ProyectoDetailView.as_view(), name='proyecto_detail'),
    path('proyectos/<int:pk>/edit/', views.ProyectoUpdateView.as_view(), name='proyecto_update'),
    path('proyectos/<int:pk>/delete/', views.ProyectoDeleteView.as_view(), name='proyecto_delete'),
    # Lotes
    path("lotes/", views.LoteListView.as_view(), name="lote_list"),
    path("lotes/create/", views.LoteCreateView.as_view(), name="lote_create"),
    path("lotes/<int:pk>/", views.LoteDetailView.as_view(), name="lote_detail"),
    path("lotes/<int:pk>/edit/", views.LoteUpdateView.as_view(), name="lote_edit"),
    path("lotes/<int:pk>/delete/", views.LoteDeleteView.as_view(), name="lote_delete"),

    # Beneficiarios
    path('beneficiarios/', views.BeneficiarioListView.as_view(), name='beneficiario_list'),
    path('beneficiarios/create/', views.BeneficiarioCreateView.as_view(), name='beneficiario_create'),
    path('beneficiarios/<int:pk>/', views.BeneficiarioDetailView.as_view(), name='beneficiario_detail'),
    path('beneficiarios/<int:pk>/edit/', views.BeneficiarioUpdateView.as_view(), name='beneficiario_update'),
    path('beneficiarios/<int:pk>/delete/', views.BeneficiarioDeleteView.as_view(), name='beneficiario_delete'),

    path('health-check/', views.health_check, name='health_check'),
    path('tramites/<int:pk>/generate-links/', views.TramiteGenerateLinksView.as_view(), name='tramite_generate_links'),
    #path('tramites/<int:pk>/send-links/', views.TramiteSendLinksView.as_view(), name='tramite_send_links'),

    # Cartas de Intención
    path('cartas-intencion/', views.CartaIntencionListView.as_view(), name='cartaintencion_list'),
    path('cartas-intencion/crear/', views.CartaIntencionCreateView.as_view(), name='cartaintencion_create'),
    path('cartas-intencion/<int:pk>/', views.CartaIntencionDetailView.as_view(), name='cartaintencion_detail'),
    path('cartas-intencion/<int:pk>/editar/', views.CartaIntencionUpdateView.as_view(), name='cartaintencion_update'),
    path('cartas-intencion/<int:pk>/eliminar/', views.CartaIntencionDeleteView.as_view(), name='cartaintencion_delete'),
    path('cartas-intencion/<int:pk>/descargar/<str:formato>/', views.CartaIntencionDownloadView.as_view(), name='cartaintencion_download'),
]


