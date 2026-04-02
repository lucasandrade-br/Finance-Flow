from django.urls import path

from . import views

app_name = 'contas'

urlpatterns = [
    path('contas/planos/', views.lista_planos_conta, name='lista_planos_conta'),
    path('contas/planos/novo/', views.novo_plano_conta, name='novo_plano_conta'),
    path('contas/planos/<int:plano_id>/editar/', views.editar_plano_conta, name='editar_plano_conta'),
    path('contas/planos/<int:plano_id>/excluir/', views.excluir_plano_conta, name='excluir_plano_conta'),
    path('contas/planos/sugerir-codigo/', views.sugerir_codigo_plano, name='sugerir_codigo_plano'),

    path('contas/tags/', views.lista_tags, name='lista_tags'),
    path('contas/tags/nova/', views.nova_tag, name='nova_tag'),
    path('contas/tags/<int:tag_id>/editar/', views.editar_tag, name='editar_tag'),
    path('contas/tags/<int:tag_id>/excluir/', views.excluir_tag, name='excluir_tag'),

    path('contas/contas-bancarias/', views.lista_contas_bancarias, name='lista_contas_bancarias'),
    path('contas/contas-bancarias/nova/', views.nova_conta_bancaria, name='nova_conta_bancaria'),
    path('contas/contas-bancarias/<int:conta_id>/editar/', views.editar_conta_bancaria, name='editar_conta_bancaria'),
    path('contas/contas-bancarias/<int:conta_id>/excluir/', views.excluir_conta_bancaria, name='excluir_conta_bancaria'),

    path('api/tags/', views.listar_tags_json, name='listar_tags_json'),
    path('api/tags/criar/', views.criar_tag_ajax, name='criar_tag_ajax'),
]
