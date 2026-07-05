from django.urls import path

from . import views

urlpatterns = [
    path('caixa/', views.caixa, name='caixa'),
    path('caixa/adicionar/', views.adicionar_item, name='adicionar_item'),
    path('caixa/remover/<int:indice>/', views.remover_item, name='remover_item'),
    path('caixa/finalizar/', views.finalizar_venda, name='finalizar_venda'),
    path('caixa/venda/<int:pk>/', views.venda_concluida, name='venda_concluida'),
    path('entrada/', views.entrada_mercadoria, name='entrada'),
    path('entrada/adicionar/', views.adicionar_lote, name='adicionar_lote'),
    path('entrada/remover/<int:indice>/', views.remover_lote, name='remover_lote'),
    path('entrada/finalizar/', views.finalizar_entrada, name='finalizar_entrada'),
    path('entrada/<int:pk>/', views.entrada_concluida, name='entrada_concluida'),
    path('produtos/', views.produtos, name='produtos'),
    path('produtos/<int:pk>/', views.produtos, name='produto_editar'),
    path('fornecedores/', views.fornecedores, name='fornecedores'),
    path('fornecedores/<int:pk>/', views.fornecedores, name='fornecedor_editar'),
]
