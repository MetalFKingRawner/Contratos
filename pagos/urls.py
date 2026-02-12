# pagos/urls.py
from django.urls import path
from . import views

app_name = 'pagos'

urlpatterns = [
    # Dashboard principal
    path('', views.DashboardPagosView.as_view(), name='dashboard'),
    
    # Detalle de trámite
    path('tramite/<int:pk>/', views.DetalleTramiteView.as_view(), name='detalle_tramite'),

    # Generar cuotas
    path('tramite/<int:tramite_id>/generar-cuotas/', 
         views.GenerarCuotasView.as_view(), 
         name='generar_cuotas'),
    
    # Generar cuotas (AJAX)
    path('tramite/<int:tramite_id>/generar-cuotas-ajax/', 
         views.GenerarCuotasAjaxView.as_view(), 
         name='generar_cuotas_ajax'),
    
    # Registrar pago (más adelante)
    path('tramite/<int:tramite_id>/registrar/', views.RegistrarPagoView.as_view(), name='registrar_pago'),
    
    # Registrar pago específico para una cuota
    path('registrar/<int:pago_id>/', views.RegistrarPagoView.as_view(), name='registrar_pago'),

    # Aplicar saldo a favor manualmente
    path('tramite/<int:tramite_id>/aplicar-saldo/', 
         views.AplicarSaldoFavorView.as_view(), 
         name='aplicar_saldo'),

    path('recibo/<int:pago_id>/pdf/', views.descargar_recibo_pago_pdf, name='descargar_recibo_pago_pdf'),

    # Generar recibo (placeholder para siguiente paso)
    #path('recibo/<int:pago_id>/', 
    #     views.GenerarReciboView.as_view(), 
    #     name='generar_recibo'),
    
    # Generar recibo (más adelante)
    #path('recibo/tramite/<int:tramite_id>/', views.GenerarReciboTramiteView.as_view(), name='generar_recibo'),
    #path('recibo/pago/<int:pago_id>/', views.GenerarReciboPagoView.as_view(), name='generar_recibo_pago'),
    
    # ... agregaremos más URLs después
]