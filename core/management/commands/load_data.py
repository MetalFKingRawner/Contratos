import json
from django.core.management.base import BaseCommand
from core.models import Proyecto, Lote, Propietario, Vendedor

class Command(BaseCommand):
    help = 'Carga datos iniciales desde JSON'

    def handle(self, *args, **options):
        with open('datos.json', 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Crear proyectos
        self.stdout.write(self.style.SUCCESS('Cargando Proyectos...'))
        for proyecto_data in data['proyectos']:
            try:
                # Comprobar si el proyecto ya existe por su ID
                Proyecto.objects.get(id=proyecto_data['id'])
                self.stdout.write(self.style.WARNING(f"Proyecto con ID {proyecto_data['id']} ya existe. Omitiendo."))
            except Proyecto.DoesNotExist:
                Proyecto.objects.create(
                    id=proyecto_data['id'],
                    nombre=proyecto_data['nombre'],
                    tipo_contrato=proyecto_data['tipo_contrato'],
                    ubicacion=proyecto_data['ubicacion']
                )
                self.stdout.write(self.style.SUCCESS(f"Proyecto '{proyecto_data['nombre']}' creado."))

        # Crear lotes
        self.stdout.write(self.style.SUCCESS('Cargando Lotes...'))
        for lote_data in data['lotes']:
            try:
                # Comprobar si el lote ya existe por su ID
                Lote.objects.get(id=lote_data['id'])
                self.stdout.write(self.style.WARNING(f"Lote con ID {lote_data['id']} ya existe. Omitiendo."))
            except Lote.DoesNotExist:
                Lote.objects.create(
                    proyecto_id=lote_data['proyecto_id'],
                    identificador=lote_data['identificador'],
                    norte=lote_data['norte'],
                    sur=lote_data['sur'],
                    este=lote_data.get('este', ''),
                    oeste=lote_data.get('oeste', ''),
                    manzana=lote_data.get('manzana')
                )
                self.stdout.write(self.style.SUCCESS(f"Lote '{lote_data['identificador']}' del proyecto {lote_data['proyecto_id']} creado."))

        # Crear propietarios
        self.stdout.write(self.style.SUCCESS('Cargando Propietarios...'))
        for prop_data in data['propietarios']:
            try:
                # Comprobar si el propietario ya existe por su INE, ya que el ID puede ser incremental
                Propietario.objects.get(ine=prop_data['ine'])
                self.stdout.write(self.style.WARNING(f"Propietario con INE {prop_data['ine']} ya existe. Omitiendo."))
            except Propietario.DoesNotExist:
                Propietario.objects.create(
                    proyecto_id=prop_data['proyecto_id'],
                    nombre_completo=prop_data['nombre_completo'],
                    sexo=prop_data.get('sexo', ''), # Añadido campo sexo
                    nacionalidad=prop_data['nacionalidad'],
                    domicilio=prop_data['domicilio'],
                    ine=prop_data['ine'],
                    telefono=prop_data['telefono'],
                    email=prop_data['email'],
                    tipo=prop_data['tipo'],
                    instrumento_publico=prop_data.get('instrumento_publico'),
                    notario_publico=prop_data.get('notario_publico'),
                    nombre_notario=prop_data.get('nombre_notario')
                )
                self.stdout.write(self.style.SUCCESS(f"Propietario '{prop_data['nombre_completo']}' creado."))

        # Crear vendedores y relaciones
        self.stdout.write(self.style.SUCCESS('Cargando Vendedores...'))
        for vend_data in data['vendedores']:
            # Usar get_or_create para evitar duplicados basados en 'ine'
            vendedor, created = Vendedor.objects.get_or_create(
                ine=vend_data['ine'],
                defaults={
                    'nombre_completo': vend_data['nombre_completo'],
                    'sexo': vend_data.get('sexo', ''), # Añadido campo sexo
                    'nacionalidad': vend_data['nacionalidad'],
                    'domicilio': vend_data['domicilio'],
                    'telefono': vend_data['telefono'],
                    'email': vend_data['email'],
                    'tipo': vend_data['tipo']
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Vendedor '{vend_data['nombre_completo']}' creado."))
            else:
                self.stdout.write(self.style.WARNING(f"Vendedor con INE {vend_data['ine']} ya existe. Actualizando relaciones de proyectos si es necesario."))

            # Añadir relaciones con proyectos
            for proyecto_id in vend_data['proyectos']:
                try:
                    proyecto = Proyecto.objects.get(id=proyecto_id)
                    if not vendedor.proyectos.filter(id=proyecto.id).exists():
                        vendedor.proyectos.add(proyecto)
                        self.stdout.write(self.style.SUCCESS(f"Vendedor '{vendedor.nombre_completo}' asociado al proyecto '{proyecto.nombre}'."))
                    else:
                        self.stdout.write(self.style.WARNING(f"Vendedor '{vendedor.nombre_completo}' ya está asociado al proyecto '{proyecto.nombre}'. Omitiendo."))
                except Proyecto.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"Proyecto con ID {proyecto_id} no encontrado para el vendedor '{vendedor.nombre_completo}'."))

        self.stdout.write(self.style.SUCCESS('Datos cargados exitosamente'))