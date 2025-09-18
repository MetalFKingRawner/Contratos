from django.db import models
from django.conf import settings
from financiamiento.models import Financiamiento
from core.models import Cliente, Vendedor, Propietario
from django.contrib.auth.models import User

class Tramite(models.Model):
    financiamiento = models.ForeignKey(Financiamiento, on_delete=models.PROTECT)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    
    # Campos para la persona que atendió (puede ser vendedor o propietario)
    vendedor = models.ForeignKey(Vendedor, on_delete=models.PROTECT, null=True, blank=True)
    propietario = models.ForeignKey(Propietario, on_delete=models.PROTECT, null=True, blank=True)

    # Nuevo campo para registrar el usuario de Django que creó el trámite
    usuario_creador = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        verbose_name="Usuario que creó el trámite",
        related_name="tramites_creados"
    )
    
    # Campos para identificar el tipo de persona seleccionada
    persona_tipo = models.CharField(
        max_length=20, 
        choices=[('vendedor', 'Vendedor'), ('propietario', 'Propietario')],
        null=True,  # Temporalmente nullable
        blank=True  # Temporalmente blank
    )
    persona_id = models.PositiveIntegerField(
        null=True,  # Temporalmente nullable
        blank=True  # Temporalmente blank
    )
    
    firma_cliente = models.TextField(
        blank=True, help_text="Data‑URL base64 de la firma del cliente"
    )
    cliente_2 = models.ForeignKey(Cliente, on_delete=models.PROTECT, null=True, blank=True, related_name='tramites_as_second')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Trámite #{self.pk} – {self.cliente.nombre_completo}"
    
    @property
    def persona(self):
        """Método para obtener la persona (vendedor o propietario) de forma uniforme"""
        if self.persona_tipo == 'vendedor' and self.vendedor:
            return self.vendedor
        elif self.persona_tipo == 'propietario' and self.propietario:
            return self.propietario
        return None
    
    def save(self, *args, **kwargs):
        # Asegurarnos de que persona_id y persona_tipo sean consistentes
        if self.vendedor:
            self.persona_tipo = 'vendedor'
            self.persona_id = self.vendedor.id
        elif self.propietario:
            self.persona_tipo = 'propietario'
            self.persona_id = self.propietario.id
        
        super().save(*args, **kwargs)

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


