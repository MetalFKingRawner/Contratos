# pagos/migrations/0002_estadospago_iniciales.py
from django.db import migrations

def crear_estados_iniciales(apps, schema_editor):
    EstadoPago = apps.get_model('pagos', 'EstadoPago')
    
    estados = [
        {'codigo': 'pendiente', 'nombre': 'Pendiente', 'color': '#ffc107', 'orden': 1},
        {'codigo': 'pagado', 'nombre': 'Pagado', 'color': '#28a745', 'orden': 2},
        {'codigo': 'atrasado', 'nombre': 'Atrasado', 'color': '#dc3545', 'orden': 3},
        {'codigo': 'parcial', 'nombre': 'Pago Parcial', 'color': '#17a2b8', 'orden': 4},
        {'codigo': 'cancelado', 'nombre': 'Cancelado', 'color': '#6c757d', 'orden': 5},
    ]
    
    for estado in estados:
        EstadoPago.objects.get_or_create(**estado)

class Migration(migrations.Migration):
    dependencies = [
        ('pagos', '0001_initial'),
    ]
    
    operations = [
        migrations.RunPython(crear_estados_iniciales),
    ]