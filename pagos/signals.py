# pagos/signals.py
from django.db.models.signals import post_migrate
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.dispatch import receiver
from .models import Pago  # Importar el modelo directamente

@receiver(post_migrate)
def crear_grupo_contabilidad(sender, **kwargs):
    # Asegurarse de que solo se ejecute para la app 'pagos'
    if sender.name == 'pagos':
        # Crear grupo "Contabilidad"
        grupo, created = Group.objects.get_or_create(name='Contabilidad')
        
        # Asignar permisos de pagos usando el modelo importado
        content_type = ContentType.objects.get_for_model(Pago)
        permisos = Permission.objects.filter(content_type=content_type)
        
        for perm in permisos:
            grupo.permissions.add(perm)
        
        print(f"✅ Grupo 'Contabilidad' creado/actualizado con permisos de pagos")