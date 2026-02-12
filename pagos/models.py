# pagos/models.py
from django.db import models
from django.contrib.auth.models import User

class EstadoPago(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default='#6c757d')  # Código hex
    orden = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['orden']
        verbose_name = 'Estado de pago'
        verbose_name_plural = 'Estados de pago'
    
    def __str__(self):
        return self.nombre

class Pago(models.Model):
    # Relación con el trámite (y a través de él, con el financiamiento)
    tramite = models.ForeignKey('workflow.Tramite', on_delete=models.CASCADE, related_name='pagos')
    
    # Información de la cuota
    numero_cuota = models.IntegerField()
    fecha_vencimiento = models.DateField()
    fecha_pago = models.DateField(null=True, blank=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Estado y detalles
    estado = models.ForeignKey(EstadoPago, on_delete=models.PROTECT)
    metodo_pago = models.CharField(max_length=50, blank=True)
    observaciones = models.TextField(blank=True)
    
    # Auditoría
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='pagos_creados')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['tramite', 'numero_cuota']
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'
        unique_together = ['tramite', 'numero_cuota']
    
    def __str__(self):
        return f"Pago #{self.numero_cuota} - {self.tramite}"
    
    @property
    def esta_atrasado(self):
        from django.utils import timezone
        if self.estado.codigo == 'pendiente' and self.fecha_vencimiento < timezone.now().date():
            return True
        return False
    
    @property
    def es_parcial(self):
        return self.monto_pagado > 0 and self.monto_pagado < self.monto

# pagos/models.py - Agregar después del modelo Pago
class SaldoAFavor(models.Model):
    """Registra saldos a favor del cliente"""
    tramite = models.ForeignKey('workflow.Tramite', on_delete=models.CASCADE, related_name='saldos_favor')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    origen = models.ForeignKey('Pago', on_delete=models.SET_NULL, null=True, blank=True, 
                               related_name='saldo_generado')
    utilizado = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_utilizacion = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Saldo a favor'
        verbose_name_plural = 'Saldos a favor'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"Saldo ${self.monto} - Trámite #{self.tramite.id}"

class HistorialPago(models.Model):
    pago = models.ForeignKey(Pago, on_delete=models.CASCADE, related_name='historial')
    accion = models.CharField(max_length=100)
    detalle = models.TextField()
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    # NUEVOS CAMPOS PARA DESGLOSE
    monto_efectivo = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Monto en efectivo de esta transacción"
    )
    monto_saldo = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Monto de saldo aplicado en esta transacción"
    )
    
    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Historial de pago'
        verbose_name_plural = 'Historial de pagos'
    
    def __str__(self):
        return f"{self.accion} - {self.fecha}"
    
# pagos/models.py - Agregar después de SaldoAFavor
class AplicacionSaldo(models.Model):
    """Registra aplicación de saldo a favor a cuotas específicas"""
    saldo = models.ForeignKey(SaldoAFavor, on_delete=models.CASCADE, related_name='aplicaciones')
    pago = models.ForeignKey(Pago, on_delete=models.CASCADE, related_name='aplicaciones_saldo')
    monto_aplicado = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = 'Aplicación de saldo'
        verbose_name_plural = 'Aplicaciones de saldo'
    
    def __str__(self):
        return f"Aplicación ${self.monto_aplicado} a Pago #{self.pago.numero_cuota}"