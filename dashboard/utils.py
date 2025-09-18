# dashboard/utils.py
import random
import string
from django.contrib.auth.models import User
from core.models import Vendedor

def generar_nombre_usuario(nombre_completo):
    """
    Genera un nombre de usuario a partir del nombre completo.
    Ejemplo: "Juan Pérez García" -> "juanpergar"
    """
    # Dividir el nombre en palabras
    palabras = nombre_completo.split()
    
    # Si hay al menos 2 palabras, tomar las primeras letras
    if len(palabras) >= 2:
        # Tomar las primeras 3 letras de las primeras 3 palabras
        usuario = ''.join([palabra[:3].lower() for palabra in palabras[:3]])
    else:
        # Si solo tiene una palabra, usar las primeras 8 letras
        usuario = palabras[0][:8].lower()
    
    # Verificar que el nombre de usuario sea único
    base_usuario = usuario
    counter = 1
    
    while User.objects.filter(username=usuario).exists():
        usuario = f"{base_usuario}{counter}"
        counter += 1
    
    return usuario

def generar_contraseña():
    """
    Genera una contraseña aleatoria con letras y números.
    Ejemplo: "aB3x9K2m"
    """
    # Combinación de letras mayúsculas, minúsculas y números
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(8))

def crear_usuario_para_vendedor(vendedor):
    """
    Crea un usuario de Django para un vendedor y devuelve las credenciales
    """
    # Generar nombre de usuario y contraseña
    username = generar_nombre_usuario(vendedor.nombre_completo)
    password = generar_contraseña()
    
    # Crear el usuario
    user = User.objects.create_user(
        username=username,
        email=vendedor.email,
        password=password,
        is_staff=False,
        is_superuser=False
    )
    
    # Asignar el usuario al vendedor
    vendedor.usuario = user
    vendedor.contraseña_temporal = password  # Guardar en texto plano
    vendedor.save()
    
    # Devolver las credenciales como diccionario
    return {
        "username": username,
        "password": password
    }