from django.db import models
from core.models import Lote  # asume que el modelo Lote ya existe

class Financiamiento(models.Model):
    TIPO_PAGO_CHOICES = [
        ('contado', 'Contado'),
        ('financiado', 'Financiado'),
    ]
    # Relación con lote; más adelante puedes cambiar a Cliente cuando exista ese modelo
    nombre_cliente   = models.CharField("Nombre del cliente", max_length=150, default="")
    lote = models.ForeignKey(Lote, on_delete=models.PROTECT, related_name='financiamientos')
    
    # Tipo de transacción
    tipo_pago = models.CharField(max_length=20, choices=TIPO_PAGO_CHOICES)
    # Datos de la tabla de financiamiento
    precio_lote       = models.DecimalField("Precio del lote", max_digits=12, decimal_places=2)
    apartado          = models.DecimalField("Apartado",      max_digits=12, decimal_places=2)
    
    # Contado
    fecha_pago_completo = models.DateField("Fecha pago completo", null=True, blank=True)
    monto_pago_completo = models.DecimalField("Pago completo", max_digits=12, decimal_places=2, null=True, blank=True)
    
    enganche           = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    fecha_enganche     = models.DateField(null=True, blank=True)
    num_mensualidades  = models.PositiveIntegerField(null=True, blank=True)
    monto_mensualidad  = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    fecha_primer_pago  = models.DateField(null=True, blank=True)
    fecha_ultimo_pago  = models.DateField(null=True, blank=True)
    monto_pago_final = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Fechas y esquema de pagos
    #fecha_inicio      = models.DateField("Fecha de inicio de pagos")
    #frecuencia        = models.CharField("Frecuencia de pago", max_length=20,
    #                                      choices=[
    #                                        ('mensual', 'Mensual'),
    #                                        ('quincenal', 'Quincenal'),
    #                                      ])
    
    
    # Guardamos aquí el detalle de la tabla de pagos (monto y fecha) en JSON
    #tabla_pagos       = models.JSONField("Esquema de pagos", blank=True, null=True,
    #                                     help_text="Lista de objetos {fecha: 'YYYY-MM-DD', monto: x.xx}")
    
    # Metadatos
    creado_en        = models.DateTimeField(auto_now_add=True)
    actualizado_en   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Financiamiento Lote {self.lote.identificador} — {self.nombre_cliente} pagos"
