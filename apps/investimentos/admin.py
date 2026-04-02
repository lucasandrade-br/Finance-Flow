from django.contrib import admin

from .models import Ativo, MetaFinanceira, MetaParcelaMensal, Ordem, Rendimento


@admin.register(Ativo)
class AtivoAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'nome', 'tipo')
    list_filter = ('tipo',)
    search_fields = ('ticker', 'nome')


@admin.register(Ordem)
class OrdemAdmin(admin.ModelAdmin):
    list_display = ('ativo', 'tipo', 'quantidade', 'preco', 'data', 'resgatar_para_orcamento')
    list_filter = ('tipo', 'resgatar_para_orcamento')
    date_hierarchy = 'data'


@admin.register(Rendimento)
class RendimentoAdmin(admin.ModelAdmin):
    list_display = ('ativo', 'valor', 'data', 'resgatar_para_orcamento')
    list_filter = ('resgatar_para_orcamento',)
    date_hierarchy = 'data'


@admin.register(MetaFinanceira)
class MetaFinanceiraAdmin(admin.ModelAdmin):
    list_display = ('nome', 'conta_bancaria', 'valor_alvo', 'data_inicio', 'data_fim', 'status')
    list_filter = ('status', 'conta_bancaria')
    search_fields = ('nome', 'conta_bancaria__nome')


@admin.register(MetaParcelaMensal)
class MetaParcelaMensalAdmin(admin.ModelAdmin):
    list_display = ('meta', 'competencia', 'valor_planejado', 'ordem_mes')
    list_filter = ('meta',)
    search_fields = ('meta__nome',)
