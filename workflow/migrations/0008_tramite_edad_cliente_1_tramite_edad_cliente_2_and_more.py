# Generated manually - combining local migrations 0009 through 0013

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0007_tramite_financiamiento_commeta_and_more'),
    ]

    operations = [
        # De 0009: es_tonameca, testigo_1_idmex, testigo_2_idmex
        migrations.AddField(
            model_name='tramite',
            name='es_tonameca',
            field=models.BooleanField(default=False, help_text='Si True: Santa María Tonameca. Si False: San Antonio de la Cal'),
        ),
        migrations.AddField(
            model_name='tramite',
            name='testigo_1_idmex',
            field=models.CharField(blank=True, help_text='Número de identificación (IDMEX) del testigo 1', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='tramite',
            name='testigo_2_idmex',
            field=models.CharField(blank=True, help_text='Número de identificación (IDMEX) del testigo 2', max_length=50, null=True),
        ),

        # De 0010: vecino
        migrations.AddField(
            model_name='tramite',
            name='vecino',
            field=models.CharField(blank=True, help_text='Referencia de ubicación cercana al domicilio del cliente (para contratos que lo requieran)', max_length=255, null=True),
        ),

        # De 0011 + 0012: edad_cliente se agrega directamente con su nombre final
        migrations.AddField(
            model_name='tramite',
            name='edad_cliente_1',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Edad del cliente al momento del contrato (solo aplica para contratos que lo requieran)', null=True),
        ),
        migrations.AddField(
            model_name='tramite',
            name='edad_cliente_2',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Edad del segundo cliente al momento del contrato (solo aplica para contratos que lo requieran)', null=True),
        ),

        # De 0013: vecino_2
        migrations.AddField(
            model_name='tramite',
            name='vecino_2',
            field=models.CharField(blank=True, help_text='Referencia de ubicación cercana al domicilio del cliente (para contratos que lo requieran)', max_length=255, null=True),
        ),
    ]
