from django.db import models
from core.models import Lote, Vendedor  # asume que el modelo Lote ya existe

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
    # NUEVOS CAMPOS
    es_cotizacion = models.BooleanField("Es cotización", default=False,
                                       help_text="Marcar si es solo una cotización/presupuesto")
    activo = models.BooleanField("Activo", default=True,
                                help_text="Desmarcar para desactivar este plan")
    
    # Metadatos
    creado_en        = models.DateTimeField(auto_now_add=True)
    actualizado_en   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Financiamiento Lote {self.lote.identificador} — {self.nombre_cliente} {self.tipo_pago}"

class CartaIntencion(models.Model):
    # Información básica del cliente (campos directos para flexibilidad)
    nombre_cliente = models.CharField("Nombre del cliente", max_length=150)
    domicilio = models.TextField("Domicilio")
    tipo_id = models.CharField("Tipo de identificación", max_length=10, default="INE")
    numero_id = models.CharField("Número de identificación", max_length=50)
    telefono_cliente = models.CharField("Teléfono", max_length=20)
    correo_cliente = models.EmailField("Correo electrónico")
    
    # Relación con Financiamiento (para obtener datos del inmueble y pagos)
    financiamiento = models.ForeignKey(
        Financiamiento, 
        on_delete=models.CASCADE,
        related_name='cartas_intencion'
    )
    
    oferta = models.DecimalField("Oferta de precio", max_digits=12, decimal_places=2)
    forma_pago = models.CharField(
        "Forma de pago",
        choices=[('Efectivo', 'Efectivo'), ('Transferencia', 'Transferencia')], 
        default='Efectivo'
    )
    # Relación con Vendedor
    vendedor = models.ForeignKey(
        Vendedor,
        on_delete=models.PROTECT,
        related_name='cartas_intencion'
    )
    
    # Campos adicionales para el builder de carta de intención
    credito_hipotecario = models.CharField(
        "Crédito hipotecario", 
        max_length=10, 
        choices=[('Sí', 'Sí'), ('No', 'No')], 
        default='No'
    )
    institucion_financiera = models.CharField(
        "Institución financiera", 
        max_length=100, 
        blank=True,
        help_text="Solo si aplica crédito hipotecario"
    )
    destinatario_apartado = models.CharField(
        "Destinatario del apartado",
        max_length=150,
        blank=True
    )
    
    # Metadatos
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Carta Intención - {self.nombre_cliente} - {self.financiamiento.lote.identificador}"

    def get_datos_financiamiento(self):
        """Método helper para acceder fácilmente a los datos del financiamiento"""
        return {
            'precio_lote': self.financiamiento.precio_lote,
            'apartado': self.financiamiento.apartado,
            'tipo_pago': self.financiamiento.tipo_pago,
            'lote_identificador': self.financiamiento.lote.identificador,
            'proyecto': self.financiamiento.lote.proyecto.nombre,
            'ubicacion': self.financiamiento.lote.proyecto.ubicacion,
        }

