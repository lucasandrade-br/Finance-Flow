from datetime import date

import django.core.validators
from django.db import migrations, models


def popular_ano_mes(apps, schema_editor):
    MacroOrcamento = apps.get_model('orcamento', 'MacroOrcamento')
    for item in MacroOrcamento.objects.all().iterator():
        if item.mes_ano:
            item.ano = item.mes_ano.year
            item.mes = item.mes_ano.month
            item.save(update_fields=['ano', 'mes'])


def reconstruir_mes_ano(apps, schema_editor):
    MacroOrcamento = apps.get_model('orcamento', 'MacroOrcamento')
    for item in MacroOrcamento.objects.all().iterator():
        if item.ano and item.mes:
            item.mes_ano = date(item.ano, item.mes, 1)
            item.save(update_fields=['mes_ano'])


class Migration(migrations.Migration):

    dependencies = [
        ('orcamento', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='macroorcamento',
            name='ano',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='macroorcamento',
            name='mes',
            field=models.IntegerField(null=True),
        ),
        migrations.RunPython(popular_ano_mes, reconstruir_mes_ano),
        migrations.AlterField(
            model_name='macroorcamento',
            name='ano',
            field=models.IntegerField(),
        ),
        migrations.AlterField(
            model_name='macroorcamento',
            name='mes',
            field=models.IntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(12)]),
        ),
        migrations.AlterUniqueTogether(
            name='macroorcamento',
            unique_together={('ano', 'mes', 'plano_conta')},
        ),
        migrations.RemoveField(
            model_name='macroorcamento',
            name='mes_ano',
        ),
    ]
