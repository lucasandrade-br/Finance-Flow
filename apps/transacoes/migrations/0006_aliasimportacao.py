from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contas', '0003_alter_planoconta_codigo'),
        ('transacoes', '0005_movimentacaoexcluida'),
    ]

    operations = [
        migrations.CreateModel(
            name='AliasImportacao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('entidade', models.CharField(choices=[('Tag', 'Tag'), ('PlanoConta', 'Plano de Conta'), ('ContaBancaria', 'Conta Bancária')], max_length=20)),
                ('valor_externo', models.CharField(max_length=180)),
                ('ativo', models.BooleanField(default=True)),
                ('conta_bancaria', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='aliases_importacao', to='contas.contabancaria')),
                ('plano_conta', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='aliases_importacao', to='contas.planoconta')),
                ('tag', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='aliases_importacao', to='contas.tag')),
            ],
            options={
                'verbose_name': 'Alias de Importação',
                'verbose_name_plural': 'Aliases de Importação',
                'ordering': ['entidade', 'valor_externo'],
                'unique_together': {('entidade', 'valor_externo')},
            },
        ),
    ]
