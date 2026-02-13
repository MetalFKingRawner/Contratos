from django.urls import path
from . import views_commeta

app_name = 'commeta'

urlpatterns = [
    
    # Configuraciones Commeta CRUD
    path('configuraciones/', views_commeta.ConfiguracionCommetaListView.as_view(), name='commeta_configuracion_list'),
    path('configuraciones/crear/', views_commeta.ConfiguracionCommetaCreateView.as_view(), name='commeta_configuracion_create'),
    path('configuraciones/<int:pk>/', views_commeta.ConfiguracionCommetaDetailView.as_view(), name='commeta_configuracion_detail'),
    path('configuraciones/<int:pk>/editar/', views_commeta.ConfiguracionCommetaUpdateView.as_view(), name='commeta_configuracion_update'),
    path('configuraciones/<int:pk>/eliminar/', views_commeta.ConfiguracionCommetaDeleteView.as_view(), name='commeta_configuracion_delete'),
    
    # Financiamientos Commeta CRUD
    path('financiamientos/', views_commeta.FinanciamientoCommetaListView.as_view(), name='commeta_financiamiento_list'),
    path('financiamientos/crear/', views_commeta.FinanciamientoCommetaCreateView.as_view(), name='commeta_financiamiento_create'),
    path('financiamientos/<int:pk>/', views_commeta.FinanciamientoCommetaDetailView.as_view(), name='commeta_financiamiento_detail'),
    path('financiamientos/<int:pk>/editar/', views_commeta.FinanciamientoCommetaUpdateView.as_view(), name='commeta_financiamiento_update'),
    path('financiamientos/<int:pk>/eliminar/', views_commeta.FinanciamientoCommetaDeleteView.as_view(), name='commeta_financiamiento_delete'),
]
