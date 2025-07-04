# reviews/urls.py
from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    # otros paths...
]
