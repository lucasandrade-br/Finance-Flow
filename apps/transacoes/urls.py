from django.urls import path

from . import views

app_name = 'transacoes'

urlpatterns = [
    path('livro-razao/', views.livro_razao, name='livro_razao'),
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
    path('futuros/<int:futuro_id>/excluir/', views.excluir_futuro, name='excluir_futuro'),
]