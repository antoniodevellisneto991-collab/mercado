"""Formulários do caixa.

Um Form (não ModelForm) porque o que o operador digita — um termo de busca —
não corresponde a um campo de modelo; a tradução termo→Produto é regra do
formulário, feita no clean().
"""
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .models import Fornecedor, Produto, Venda


def resolver_produto(termo):
    """Traduz o que o operador digitou em um Produto ativo.

    Ordem: código de barras exato → nome exato → nome parcial (se único).
    Levanta ValidationError com mensagem amigável nos demais casos.
    """
    ativos = Produto.objects.filter(ativo=True)
    produto = ativos.filter(ean=termo).first() or ativos.filter(nome__iexact=termo).first()
    if produto is None:
        candidatos = list(ativos.filter(nome__icontains=termo)[:3])
        if len(candidatos) == 1:
            produto = candidatos[0]
        elif not candidatos:
            raise ValidationError(f'Nenhum produto ativo encontrado para “{termo}”.')
        else:
            nomes = ', '.join(c.nome for c in candidatos)
            raise ValidationError(f'“{termo}” é ambíguo ({nomes}…) — complete o nome.')
    return produto


class AdicionarItemForm(forms.Form):
    busca = forms.CharField(
        label='Produto',
        help_text='Nome ou código de barras',
        widget=forms.TextInput(attrs={'list': 'produtos', 'autofocus': True, 'autocomplete': 'off'}),
    )
    quantidade = forms.DecimalField(
        label='Quantidade',
        min_value=Decimal('0.001'),
        max_digits=10,
        decimal_places=3,
        initial=1,
        widget=forms.NumberInput(attrs={'step': '0.001'}),
    )

    def clean(self):
        dados = super().clean()
        termo = (dados.get('busca') or '').strip()
        if termo:
            dados['produto'] = resolver_produto(termo)
        return dados


class FinalizarVendaForm(forms.Form):
    forma_pagamento = forms.ChoiceField(
        label='Pagamento',
        choices=Venda.FormaPagamento.choices,
        widget=forms.RadioSelect,
        initial=Venda.FormaPagamento.DINHEIRO,
    )


class AdicionarLoteForm(forms.Form):
    """Uma linha do recebimento: produto + quantidade + custo + validade."""

    busca = forms.CharField(
        label='Produto',
        help_text='Nome ou código de barras',
        widget=forms.TextInput(attrs={'list': 'produtos', 'autofocus': True, 'autocomplete': 'off'}),
    )
    quantidade = forms.DecimalField(
        label='Quantidade recebida',
        min_value=Decimal('0.001'), max_digits=10, decimal_places=3,
        widget=forms.NumberInput(attrs={'step': '0.001'}),
    )
    custo_unitario = forms.DecimalField(
        label='Custo unitário (R$)',
        min_value=Decimal('0'), max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01'}),
    )
    validade = forms.DateField(
        label='Validade', required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    numero_lote = forms.CharField(label='Nº do lote', required=False, max_length=50)

    def clean(self):
        dados = super().clean()
        termo = (dados.get('busca') or '').strip()
        if termo:
            dados['produto'] = resolver_produto(termo)
            if dados['produto'].perecivel and not dados.get('validade'):
                raise ValidationError(
                    f'{dados["produto"].nome} é perecível — informe a validade do lote.'
                )
        return dados


class FinalizarEntradaForm(forms.Form):
    fornecedor = forms.ModelChoiceField(
        label='Fornecedor', queryset=Fornecedor.objects.all(),
        required=False, empty_label='— sem fornecedor —',
    )
    observacao = forms.CharField(
        label='Observação', required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
    )


class ProdutoForm(forms.ModelForm):
    """Cadastro de produto. ultimo_custo fica de fora: quem escreve nele é a entrada."""

    class Meta:
        model = Produto
        fields = ['nome', 'categoria', 'ean', 'unidade', 'preco_venda',
                  'estoque_minimo', 'perecivel', 'ativo']

    def clean_ean(self):
        # CharField com unique: dois EAN vazios ('') colidiriam.
        # Vazio precisa virar None — NULL não participa do unique.
        return self.cleaned_data['ean'] or None


class FornecedorForm(forms.ModelForm):
    class Meta:
        model = Fornecedor
        fields = ['nome', 'tipo', 'observacao']
        widgets = {'observacao': forms.Textarea(attrs={'rows': 2})}
