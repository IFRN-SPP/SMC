import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoramento', '0007_alerta_resolvido_alerta_resolvido_em_alerta_tipo'),
    ]

    operations = [
        migrations.AddField(
            model_name='leituratelemetria',
            name='temperatura_agua',
            field=models.FloatField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(-55), django.core.validators.MaxValueValidator(125)], verbose_name='Temperatura da água (°C)'),
        ),
        migrations.AddField(
            model_name='leituratelemetria',
            name='temperatura_ar',
            field=models.FloatField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(-55), django.core.validators.MaxValueValidator(125)], verbose_name='Temperatura do ar (°C)'),
        ),
        migrations.AddField(
            model_name='leituratelemetria',
            name='umidade_ar',
            field=models.FloatField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], verbose_name='Umidade relativa do ar (%)'),
        ),
        migrations.AddField(
            model_name='leituratelemetria',
            name='qualidade_agua_ppm',
            field=models.FloatField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Qualidade da água (ppm)'),
        ),
        migrations.AddField(
            model_name='leituratelemetria',
            name='tensao_bateria',
            field=models.FloatField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], verbose_name='Tensão da bateria (V)'),
        ),
        migrations.AddField(
            model_name='leituratelemetria',
            name='tensao_placa_solar',
            field=models.FloatField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], verbose_name='Tensão da placa solar (V)'),
        ),
    ]
