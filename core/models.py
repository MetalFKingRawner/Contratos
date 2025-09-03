# models.py
from django.db import models

class Proyecto(models.Model):
    nombre = models.CharField(max_length=100)
    tipo_contrato = models.CharField(max_length=50)
    ubicacion = models.TextField()
    fecha_emision_documento = models.TextField(default='')
    autoridad = models.TextField(default='')
    fecha_emision_contrato = models.TextField(default='')

    def __str__(self):
        return self.nombre

class Lote(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='lotes')
    identificador = models.CharField(max_length=20)
    norte = models.CharField(max_length=100)
    sur = models.CharField(max_length=100)
    este = models.CharField(max_length=100)  # Cambiado de 'oriente' a 'este'
    oeste = models.CharField(max_length=100)  # Cambiado de 'poniente' a 'oeste'
    manzana = models.CharField(max_length=20, blank=True, null=True)  # Solo para algunos proyectos
    activo      = models.BooleanField(default=True)  # ← NUEVO campo

    def __str__(self):
        return f"{self.proyecto.nombre} – Lote {self.identificador}"

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

    nombre_completo = models.CharField(max_length=100)
    sexo                  = models.CharField("Sexo", max_length=1, choices=SEXO_CHOICES, default='M')
    nacionalidad = models.CharField(max_length=50)
    domicilio = models.TextField()
    ine = models.CharField(max_length=20)
    telefono = models.CharField(max_length=15)
    email = models.EmailField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    proyectos = models.ManyToManyField(Proyecto, related_name='vendedores')

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





