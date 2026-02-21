#!/bin/bash
set -e

echo "Recalculando superficies nulas..."
python manage.py shell -c "
from core.models import Lote
lotes = Lote.objects.filter(superficie_m2__isnull=True)
count = lotes.count()
for lote in lotes:
    lote.save()
print(f'{count} lotes actualizados.')
"

echo "Iniciando servidor..."
exec gunicorn inmobiliaria.wsgi:application --bind 0.0.0.0:8000
