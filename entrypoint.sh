echo "Recalculando superficies nulas..."
python manage.py shell -c "
from core.models import Lote
lotes = Lote.objects.filter(superficie_m2__isnull=True)
count = lotes.count()
for lote in lotes:
    lote.save()
print(f'{count} lotes actualizados.')
"
