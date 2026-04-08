from django.contrib import admin

from .models import Ciclo, Cofre, MacroOrcamento, MovimentacaoOrcamento


@admin.register(Ciclo)
class CicloAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'data_inicio', 'data_fim', 'status', 'saldo_inicial_projetado')
    list_filter = ('status',)
    list_editable = ('status',)


@admin.register(MacroOrcamento)
class MacroOrcamentoAdmin(admin.ModelAdmin):
    list_display = ('plano_conta', 'ano', 'mes', 'valor_teto')
    list_filter = ('ano', 'mes')
    search_fields = ('plano_conta__nome',)


@admin.register(Cofre)
class CofreAdmin(admin.ModelAdmin):
    list_display = ('nome', 'valor_meta', 'saldo_atual', 'status', 'data_alvo')
    list_filter = ('status',)
    search_fields = ('nome',)


@admin.register(MovimentacaoOrcamento)
class MovimentacaoOrcamentoAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'plano_conta', 'conta_bancaria', 'frequencia', 'valor', 'status_ativa')
    list_filter = ('tipo', 'frequencia', 'status_ativa')
    search_fields = ('descricao', 'plano_conta__nome', 'plano_conta__codigo')
