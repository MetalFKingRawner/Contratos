from django.urls import path
from .views import (
    FinanciamientoListView, 
    FinanciamientoCreateView, 
    FinanciamientoUpdateView
)

app_name = 'financiamiento'

urlpatterns = [
    path('',       FinanciamientoListView.as_view(),   name='list'),
    path('nuevo/', FinanciamientoCreateView.as_view(), name='create'),
    path('<int:pk>/editar/', FinanciamientoUpdateView.as_view(), name='edit'),
]
