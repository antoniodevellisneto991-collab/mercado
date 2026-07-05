"""Lógica de negócio que não pertence a nenhum modelo isolado.

Modelos guardam dados e regras locais (um clean(), um save()); quando a regra
atravessa vários modelos — como a baixa FEFO, que toca ItemVenda, Lote e
BaixaLote ao mesmo tempo — ela ganha um lugar próprio. Views e admin chamam
daqui; testes testam daqui.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from .models import BaixaLote, ItemVenda


@transaction.atomic
def baixar_estoque_fefo(item: ItemVenda) -> Decimal:
    """Consome lotes do produto por FEFO: vence primeiro, sai primeiro.

    Percorre os lotes com saldo, do vencimento mais próximo para o mais
    distante (sem validade por último), descontando até cobrir a quantidade
    do item. Cada desconto vira um BaixaLote (auditoria). O que não couber
    em lote nenhum fica registrado em item.quantidade_sem_lote — a venda
    nunca é bloqueada; a diferença vira discrepância a investigar.

    Devolve a quantidade sem cobertura (0 quando o estoque bastou).
    """
    restante = item.quantidade

    lotes = (
        item.produto.lotes
        .filter(quantidade_atual__gt=0)
        .order_by(F('validade').asc(nulls_last=True), 'id')
        .select_for_update()
    )

    for lote in lotes:
        if restante <= 0:
            break
        usar = min(lote.quantidade_atual, restante)
        lote.quantidade_atual -= usar
        lote.save(update_fields=['quantidade_atual'])
        BaixaLote.objects.create(item=item, lote=lote, quantidade=usar)
        restante -= usar

    if restante > 0:
        item.quantidade_sem_lote = restante
        item.save(update_fields=['quantidade_sem_lote'])

    return restante
