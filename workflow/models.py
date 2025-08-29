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
