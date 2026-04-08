from django.urls import path

from . import views

app_name = 'transacoes'

urlpatterns = [
    path('livro-razao/', views.livro_razao, name='livro_razao'),
    path('importacao/transacoes/', views.importar_transacoes, name='importar_transacoes'),
    path('importacao/transacoes/confirmar/', views.confirmar_importacao_transacoes, name='confirmar_importacao_transacoes'),
    path('importacao/transacoes/modelo-xlsx/', views.baixar_modelo_importacao_xlsx, name='baixar_modelo_importacao_xlsx'),
    path('importacao/aliases/', views.lista_aliases_importacao, name='lista_aliases_importacao'),
    path('importacao/aliases/novo/', views.novo_alias_importacao, name='novo_alias_importacao'),
    path('importacao/aliases/<int:alias_id>/excluir/', views.excluir_alias_importacao, name='excluir_alias_importacao'),
    path('importacao/sugerir-correspondencia/', views.sugerir_correspondencia_importacao, name='sugerir_correspondencia_importacao'),
    path('nova-transacao/', views.nova_transacao, name='nova_transacao'),
    path('movimentacoes/<int:movimentacao_id>/excluir/', views.excluir_movimentacao, name='excluir_movimentacao'),
    path('movimentacoes-excluidas/<int:item_id>/restaurar/', views.restaurar_movimentacao_excluida, name='restaurar_movimentacao_excluida'),
    path('painel-edicao/<str:origem>/<int:registro_id>/', views.painel_edicao, name='painel_edicao'),
    path('partida-dupla/', views.partida_dupla, name='partida_dupla'),
    path('recorrentes/', views.lista_recorrentes, name='lista_recorrentes'),
    path('recorrentes/nova/', views.nova_recorrente, name='nova_recorrente'),
    path('recorrentes/<int:recorrente_id>/excluir/', views.excluir_recorrente, name='excluir_recorrente'),
    path('futuros/', views.lista_futuros, name='lista_futuros'),
    path('futuros/novo/', views.novo_futuro, name='novo_futuro'),
    path('futuros/<int:futuro_id>/adiantar/', views.adiantar_futuro, name='adiantar_futuro'),
    path('futuros/<int:futuro_id>/excluir/', views.excluir_futuro, name='excluir_futuro'),
]