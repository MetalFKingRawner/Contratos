# Generated by Django 5.0.3 on 2025-07-02 17:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_cliente_sexo'),
    ]

    operations = [
        migrations.AddField(
            model_name='propietario',
            name='sexo',
            field=models.CharField(choices=[('M', 'Masculino'), ('F', 'Femenino')], default='M', max_length=1, verbose_name='Sexo'),
        ),
        migrations.AddField(
            model_name='vendedor',
            name='sexo',
            field=models.CharField(choices=[('M', 'Masculino'), ('F', 'Femenino')], default='M', max_length=1, verbose_name='Sexo'),
        ),
    ]
