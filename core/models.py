# models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from workflow.utils import calcular_superficie

class Proyecto(models.Model):
    TIPO_PROYECTO_CHOICES = [
        ('normal', 'Proyecto Normal'),
        ('commeta', 'Commeta Community'),
    ]
    nombre = models.CharField(max_length=100)
    tipo_contrato = models.CharField(max_length=50)
    ubicacion = models.TextField()
    fecha_emision_documento = models.TextField(default='')
    autoridad = models.TextField(default='')
    fecha_emision_contrato = models.TextField(default='')
    # NUEVO CAMPO
    tipo_proyecto = models.CharField(
        max_length=20, 
        choices=TIPO_PROYECTO_CHOICES, 
        default='normal'
    )

    # NUEVOS CAMPOS PARA DOCUMENTOS ESPECIALES
    incluir_cesion_derechos = models.BooleanField(
        default=False,
        verbose_name="Incluir Cesión de Derechos",
        help_text="Indica si el proyecto cuenta con documento de Cesión de Derechos"
    )
    
    incluir_constancia_cesion = models.BooleanField(
        default=False,
        verbose_name="Incluir Constancia de Cesión",
        help_text="Indica si el proyecto cuenta con Constancia de Cesión de Derechos"
    )
    
    incluir_constancia_posesion = models.BooleanField(  # Nota: corregí "possession" a "posesion"
        default=False,
        verbose_name="Incluir Constancia de Posesión",
        help_text="Indica si el proyecto cuenta con Constancia de Posesión"
    )

    def __str__(self):
        return self.nombre

    # NUEVO MÉTODO
    def es_ejido(self):
        """Verifica si el proyecto es de tipo EJIDO"""
        return self.tipo_contrato.upper() == "EJIDO"
    
    # NUEVA PROPIEDAD
    @property
    def documentos_especiales_habilitados(self):
        """Devuelve True si el proyecto puede tener documentos especiales"""
        return self.es_ejido()

class Lote(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='lotes')
    identificador = models.CharField(max_length=20)
    norte = models.CharField(max_length=100)
    sur = models.CharField(max_length=100)
    este = models.CharField(max_length=100)  # Cambiado de 'oriente' a 'este'
    oeste = models.CharField(max_length=100)  # Cambiado de 'poniente' a 'oeste'
    manzana = models.CharField(max_length=20, blank=True, null=True)  # Solo para algunos proyectos
    activo      = models.BooleanField(default=True)  # ← NUEVO campo

    superficie_m2 = models.DecimalField(
        max_digits=10, decimal_places=2,
        blank=True, null=True,
        help_text="Si se deja vacío, se calcula automáticamente a partir de las medidas."
    )

    def save(self, *args, **kwargs):
        if self.superficie_m2 is None:
            self.superficie_m2 = calcular_superficie(self.norte, self.sur, self.este, self.oeste)
        super().save(*args, **kwargs)

    @property
    def superficie(self):
        if self.superficie_m2 is not None:
            return float(self.superficie_m2)
        return calcular_superficie(self.norte, self.sur, self.este, self.oeste)

    
    def __str__(self):
        return f"{self.proyecto.nombre} – Lote {self.identificador}"
    
    @property
    def es_commeta(self):
        """Propiedad para verificar si el lote pertenece a un proyecto Commeta"""
        return self.proyecto.tipo_proyecto == 'commeta'
# En core/models.py - ACTUALIZAR ConfiguracionCommeta
class ConfiguracionCommeta(models.Model):
    ZONA_CHOICES = [
        ('ambar', 'Ambar'),
        ('aqua', 'Aqua'),
        ('magnetita', 'Magnetita'),
        ('platino', 'Platino'),
    ]
    
    TIPO_ESQUEMA_CHOICES = [
        ('mensualidades_fijas', 'Mensualidades Fijas'),
        ('meses_fuertes', 'Meses Fuertes'),
    ]
    
    lote = models.OneToOneField(
        Lote, 
        on_delete=models.CASCADE, 
        related_name='configuracion_commeta'
    )
    zona = models.CharField(max_length=50, choices=ZONA_CHOICES)
    
    # NUEVO: Tipo de esquema de pagos
    tipo_esquema = models.CharField(
        max_length=20, 
        choices=TIPO_ESQUEMA_CHOICES,
        default='meses_fuertes'
    )
    
    precio_base = models.DecimalField(max_digits=12, decimal_places=2)
    apartado_sugerido = models.DecimalField(max_digits=12, decimal_places=2, default=3500)
    enganche_sugerido = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Para esquema de mensualidades fijas
    mensualidad_sugerida = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Para esquema de mensualidades fijas"
    )
    
    # Para esquema de meses fuertes
    monto_mensualidad_normal = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Monto de mensualidad normal en esquema de meses fuertes"
    )
    monto_mes_fuerte = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Monto de mes fuerte"
    )
    monto_pago_final = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Monto del último pago (puede ser diferente al mes fuerte)"
    )
    frecuencia_meses_fuertes = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Cada cuántos meses se repite un mes fuerte"
    )
    
    # NUEVO: Para meses fuertes con distribución específica
    meses_fuertes_especificos = models.JSONField(
        default=list,
        blank=True,
        null=True,
        help_text="Lista específica de números de meses que son fuertes (ej: [3,8,15,22,29,36])"
    )
    
    # NUEVO: Para esquemas personalizados futuros
    esquema_personalizado = models.JSONField(
        default=dict,
        blank=True,
        help_text="Estructura completa de pagos para esquemas personalizados futuros"
    )
    
    # NUEVO: Para desactivar configuraciones obsoletas
    activo = models.BooleanField(
        default=True,
        help_text="Desactivar configuraciones que ya no se usen"
    )
    
    total_meses = models.PositiveIntegerField()

    cantidad_meses_fuertes_sugerida = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Cantidad sugerida de meses fuertes para esquemas predefinidos"
    )
    
    class Meta:
        verbose_name = "Configuración Commeta"
        verbose_name_plural = "Configuraciones Commeta"

    def __str__(self):
        return f"Config Commeta - {self.lote.identificador} ({self.zona})"

class Propietario(models.Model):
    TIPO_CHOICES = [
        ('propietario', 'Propietario'),
        ('apoderado', 'Apoderado'),
    ]
    SEXO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
    ]
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='propietario')
    nombre_completo = models.CharField(max_length=100)
    sexo                  = models.CharField("Sexo", max_length=1, choices=SEXO_CHOICES, default='M')
    nacionalidad = models.CharField(max_length=50)
    domicilio = models.TextField()
    ine = models.CharField(max_length=20)
    telefono = models.CharField(max_length=15)
    email = models.EmailField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    instrumento_publico = models.CharField(max_length=50, blank=True, null=True)
    notario_publico = models.CharField(max_length=50, blank=True, null=True)
    nombre_notario = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.nombre_completo

class Vendedor(models.Model):
    TIPO_CHOICES = [
        ('vendedor', 'Vendedor'),
        ('apoderado', 'Apoderado'),
    ]
    SEXO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
    ]

    # Relación con el usuario de Django
    usuario = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        related_name='vendedor',
        null=True,
        blank=True
    )

    nombre_completo = models.CharField(max_length=100)
    sexo                  = models.CharField("Sexo", max_length=1, choices=SEXO_CHOICES, default='M')
    nacionalidad = models.CharField(max_length=50)
    domicilio = models.TextField()
    ine = models.CharField(max_length=20)
    telefono = models.CharField(max_length=15)
    email = models.EmailField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    proyectos = models.ManyToManyField(Proyecto, related_name='vendedores')

    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    ultima_modificacion = models.DateTimeField(auto_now=True)
    contraseña_temporal = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.nombre_completo

class Cliente(models.Model):
    SEXO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
    ]

    nombre_completo = models.CharField("Nombre completo", max_length=150)
    sexo                  = models.CharField("Sexo", max_length=1, choices=SEXO_CHOICES, default='M')
    rfc             = models.CharField("RFC", max_length=13, blank=True, null=True)
    domicilio       = models.TextField("Domicilio")
    telefono        = models.CharField("Teléfono", max_length=20)
    email           = models.EmailField("Correo electrónico", blank=True)
    ocupacion       = models.CharField("Ocupación", max_length=100, blank=True)
    estado_civil    = models.CharField("Estado civil", max_length=50, blank=True)
    nacionalidad    = models.CharField("Nacionalidad", max_length=50, blank=True)
    originario      = models.CharField("Lugar de origen", max_length=100, blank=True)
    tipo_id         = models.CharField("Tipo de identificación", max_length=50)
    numero_id       = models.CharField("Número de identificación", max_length=50)
    # Opcionalmente, un campo para guardar el nombre de quien firma:
    #nombre_firma_cliente  = models.CharField("Nombre para firma del cliente", max_length=150, blank=True)
    #nombre_firma_vendedor = models.CharField("Nombre para firma del vendedor", max_length=150, blank=True)

    creado_en      = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre_completo

class Beneficiario(models.Model):
    SEXO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
    ]

    nombre_completo = models.CharField("Nombre completo", max_length=150)
    sexo            = models.CharField("Sexo", max_length=1, choices=SEXO_CHOICES, default='M', blank=True)
    telefono        = models.CharField("Teléfono", max_length=20, blank=True)
    email           = models.EmailField("Correo electrónico", blank=True)
    numero_id       = models.CharField("Número de identificación", max_length=50, blank=True)

    creado_en      = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre_completo




