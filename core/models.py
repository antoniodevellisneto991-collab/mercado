from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class Produto(models.Model):
    """Catálogo de produtos. Não guarda quantidade — isso é responsabilidade de Lote."""

    class Categoria(models.TextChoices):
        MERCEARIA = 'mercearia', 'Mercearia'
        BEBIDAS = 'bebidas', 'Bebidas'
        HORTIFRUTI = 'hortifruti', 'Hortifrúti'
        LIMPEZA = 'limpeza', 'Limpeza'

    class Unidade(models.TextChoices):
        UNIDADE = 'un', 'Unidade'
        QUILO = 'kg', 'Quilo'

    nome = models.CharField(max_length=150)
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    ean = models.CharField('código de barras (EAN)', max_length=13, unique=True, null=True, blank=True)
    unidade = models.CharField(max_length=2, choices=Unidade.choices)
    preco_venda = models.DecimalField(max_digits=10, decimal_places=2)
    ultimo_custo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estoque_minimo = models.DecimalField(max_digits=10, decimal_places=3)
    perecivel = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Fornecedor(models.Model):
    class Tipo(models.TextChoices):
        DISTRIBUIDORA = 'distribuidora', 'Distribuidora'
        ATACADO = 'atacado', 'Atacado'
        VAREJO_VIZINHO = 'varejo_vizinho', 'Varejo vizinho'

    nome = models.CharField(max_length=150)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ['nome']
        verbose_name_plural = 'fornecedores'

    def __str__(self):
        return self.nome


class Entrada(models.Model):
    """Um recebimento de mercadoria. Pode conter vários lotes (um por produto recebido)."""

    data = models.DateField(default=timezone.localdate)
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.PROTECT, null=True, blank=True, related_name='entradas'
    )
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ['-data']

    def __str__(self):
        return f'Entrada #{self.pk} — {self.data:%d/%m/%Y}'


class Lote(models.Model):
    """A unidade real de estoque: quanto entrou, quanto ainda resta, a que custo e até quando."""

    entrada = models.ForeignKey(Entrada, on_delete=models.CASCADE, related_name='lotes')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='lotes')
    quantidade_inicial = models.DecimalField(max_digits=10, decimal_places=3)
    quantidade_atual = models.DecimalField(max_digits=10, decimal_places=3)
    custo_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    validade = models.DateField(null=True, blank=True)
    numero_lote = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = [models.F('validade').asc(nulls_last=True)]

    def save(self, *args, **kwargs):
        if self.quantidade_atual is None:
            self.quantidade_atual = self.quantidade_inicial
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Lote #{self.pk} — {self.produto.nome}'


class Ajuste(models.Model):
    """Correção manual de um lote: perda, quebra, consumo interno ou acerto de contagem.

    quantidade é assinada: negativo tira do lote (perda/quebra/consumo),
    positivo corrige a contagem para cima.
    """

    class Motivo(models.TextChoices):
        PERDA = 'perda', 'Perda'
        QUEBRA = 'quebra', 'Quebra'
        CONSUMO = 'consumo', 'Consumo'
        CONTAGEM = 'contagem', 'Ajuste de contagem'

    lote = models.ForeignKey(Lote, on_delete=models.PROTECT, related_name='ajustes')
    quantidade = models.DecimalField(max_digits=10, decimal_places=3)
    motivo = models.CharField(max_length=20, choices=Motivo.choices)
    data = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data']

    def clean(self):
        """Impede ajuste que deixaria o lote com saldo negativo."""
        if self.lote_id and self.quantidade is not None:
            if self.lote.quantidade_atual + self.quantidade < 0:
                raise ValidationError(
                    f'O lote tem apenas {self.lote.quantidade_atual}; '
                    f'este ajuste deixaria o saldo negativo.'
                )

    def save(self, *args, **kwargs):
        """Um ajuste é um lançamento: ao ser criado, aplica seu efeito no lote.

        Só na criação — ajustes não são editados nem apagados (livro-razão).
        O admin reforça isso desabilitando change/delete.
        """
        criando = self.pk is None
        with transaction.atomic():
            super().save(*args, **kwargs)
            if criando:
                Lote.objects.filter(pk=self.lote_id).update(
                    quantidade_atual=models.F('quantidade_atual') + self.quantidade
                )

    def __str__(self):
        return f'Ajuste #{self.pk} — {self.motivo} ({self.quantidade})'


class Venda(models.Model):
    """Uma passagem pelo caixa. Os produtos vendidos ficam em ItemVenda."""

    class FormaPagamento(models.TextChoices):
        DINHEIRO = 'dinheiro', 'Dinheiro'
        PIX = 'pix', 'PIX'
        CARTAO = 'cartao', 'Cartão'

    data_hora = models.DateTimeField(auto_now_add=True)
    forma_pagamento = models.CharField(max_length=10, choices=FormaPagamento.choices)

    class Meta:
        ordering = ['-data_hora']

    @property
    def total(self):
        return sum((item.subtotal for item in self.itens.all()), Decimal('0'))

    def __str__(self):
        return f'Venda #{self.pk} — {self.data_hora:%d/%m/%Y %H:%M}'


class ItemVenda(models.Model):
    """Uma linha da venda: produto, quantidade e o preço CONGELADO no momento.

    preco_unitario é copiado de Produto.preco_venda na hora — se o preço do
    produto mudar amanhã, o histórico de vendas não muda junto.
    """

    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='itens_venda')
    quantidade = models.DecimalField(max_digits=10, decimal_places=3)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    quantidade_sem_lote = models.DecimalField(
        max_digits=10, decimal_places=3, default=Decimal('0'),
        help_text='Parte vendida sem cobertura de lote (estoque do sistema era menor que a prateleira). Discrepância a investigar.',
    )

    def save(self, *args, **kwargs):
        if self.preco_unitario is None:
            self.preco_unitario = self.produto.preco_venda
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return self.quantidade * self.preco_unitario

    def __str__(self):
        return f'{self.produto.nome} × {self.quantidade}'


class BaixaLote(models.Model):
    """Trilha de auditoria da baixa FEFO: qual lote atendeu qual item, e quanto.

    Sem isso, saberíamos que o estoque diminuiu, mas não de onde saiu —
    e perderíamos a base para custo por venda (CMV) no futuro.
    """

    item = models.ForeignKey(ItemVenda, on_delete=models.CASCADE, related_name='baixas')
    lote = models.ForeignKey(Lote, on_delete=models.PROTECT, related_name='baixas')
    quantidade = models.DecimalField(max_digits=10, decimal_places=3)

    class Meta:
        verbose_name = 'baixa de lote'
        verbose_name_plural = 'baixas de lote'

    def __str__(self):
        return f'{self.quantidade} do lote #{self.lote_id} para item #{self.item_id}'
