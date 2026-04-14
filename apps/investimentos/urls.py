from django.urls import path

from . import views

app_name = 'investimentos'

urlpatterns = [
	path('painel/', views.painel_investimentos, name='painel_investimentos'),
    path('relatorios/', views.relatorios_investimentos, name='relatorios_investimentos'),
    path('relatorios/<int:ano>/', views.relatorios_investimentos, name='relatorios_investimentos_ano'),
    path('ativos/', views.gestao_ativos, name='gestao_ativos'),
    path('historico/', views.historico_investimentos, name='historico_investimentos'),
    path('importacao/xlsx/', views.importar_operacoes_xlsx, name='importar_operacoes_xlsx'),
    path('importacao/xlsx/modelo/', views.baixar_modelo_importacao_xlsx, name='baixar_modelo_importacao_xlsx'),
	path('ordens/nova/', views.nova_ordem, name='nova_ordem'),
	path('rendimentos/novo/', views.novo_rendimento, name='novo_rendimento'),
    path('metas/', views.lista_metas, name='lista_metas'),
    path('metas/nova/', views.nova_meta, name='nova_meta'),
    path('metas/<int:meta_id>/roteiro/', views.roteiro_meta, name='roteiro_meta'),
    path('metas/<int:meta_id>/painel/', views.painel_meta, name='painel_meta'),
    path('metas/<int:meta_id>/editar/', views.editar_meta, name='editar_meta'),
    path('metas/<int:meta_id>/excluir/', views.excluir_meta, name='excluir_meta'),
]
