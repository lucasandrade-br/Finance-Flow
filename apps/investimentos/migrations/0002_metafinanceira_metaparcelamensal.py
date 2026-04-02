from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contas', '0001_initial'),
        ('investimentos', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MetaFinanceira',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nome', models.CharField(max_length=180)),
                ('valor_alvo', models.DecimalField(decimal_places=2, max_digits=12)),
                ('data_inicio', models.DateField()),
                ('data_fim', models.DateField()),
                ('status', models.CharField(choices=[('Rascunho', 'Rascunho'), ('Ativa', 'Ativa'), ('Concluida', 'Concluída'), ('Cancelada', 'Cancelada')], default='Ativa', max_length=10)),
                ('conta_bancaria', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='metas_financeiras', to='contas.contabancaria')),
            ],
            options={
                'verbose_name': 'Meta Financeira',
                'verbose_name_plural': 'Metas Financeiras',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MetaParcelaMensal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('competencia', models.DateField(help_text='Use o primeiro dia do mês como referência da competência.')),
                ('valor_planejado', models.DecimalField(decimal_places=2, max_digits=12)),
                ('ordem_mes', models.PositiveIntegerField(default=1)),
                ('observacao', models.CharField(blank=True, max_length=255)),
                ('meta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parcelas_mensais', to='investimentos.metafinanceira')),
            ],
            options={
                'verbose_name': 'Parcela Mensal da Meta',
                'verbose_name_plural': 'Parcelas Mensais das Metas',
                'ordering': ['meta_id', 'competencia', 'ordem_mes'],
            },
        ),
        migrations.AddConstraint(
            model_name='metaparcelamensal',
            constraint=models.UniqueConstraint(fields=('meta', 'competencia'), name='uniq_meta_competencia'),
        ),
    ]
