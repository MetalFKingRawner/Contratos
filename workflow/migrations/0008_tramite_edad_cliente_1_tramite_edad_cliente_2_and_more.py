from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0007_tramite_financiamiento_commeta_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tramite',
            name='firma_cliente2',
            field=models.TextField(blank=True, help_text='Data-URL base64 de la firma del segundo cliente'),
        ),
        migrations.AlterField(
            model_name='tramite',
            name='firma_vendedor',
            field=models.TextField(blank=True, help_text='Data‑URL base64 de la firma del vendedor'),
        ),
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
        migrations.AddField(
            model_name='tramite',
            name='vecino',
            field=models.CharField(blank=True, help_text='Referencia de ubicación cercana al domicilio del cliente (para contratos que lo requieran)', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='tramite',
            name='vecino_2',
            field=models.CharField(blank=True, help_text='Referencia de ubicación cercana al domicilio del cliente (para contratos que lo requieran)', max_length=255, null=True),
        ),
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
    ]
