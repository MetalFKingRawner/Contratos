from django.db import models
from django.conf import settings
from financiamiento.models import Financiamiento
from core.models import Cliente, Vendedor

class Tramite(models.Model):
    financiamiento = models.ForeignKey(Financiamiento, on_delete=models.PROTECT)
    cliente        = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    vendedor       = models.ForeignKey(Vendedor, on_delete=models.PROTECT)
    firma_cliente  = models.TextField(
        blank=True, help_text="Data‑URL base64 de la firma del cliente"
    )
    cliente_2 = models.ForeignKey(Cliente, on_delete=models.PROTECT, null=True, blank=True, related_name='tramites_as_second')
    creado_en      = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Trámite #{self.pk} – {self.cliente.nombre_completo}"

# workflow/models.py
class ClausulasEspeciales(models.Model):
    tramite = models.OneToOneField(
        'Tramite', 
        on_delete=models.CASCADE, 
        related_name='clausulas_especiales'
    )
    clausula_pago = models.TextField(
        blank=True, 
        verbose_name="Cláusula de Pago Personalizada"
    )
    clausula_deslinde = models.TextField(
        blank=True, 
        verbose_name="Cláusula de Deslinde Personalizada"
    )
    clausula_promesa = models.TextField(
        blank=True, 
        verbose_name="Cláusula de Promesa Personalizada"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cláusulas Especiales del Trámite"
        verbose_name_plural = "Cláusulas Especiales de los Trámites"

    def __str__(self):
        return f"Cláusulas especiales - Trámite #{self.tramite.id}"
