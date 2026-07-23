"""Tela do caixa: carrinho na sessão, estoque só é tocado ao finalizar.

O carrinho é uma lista de dicts na sessão do navegador:
    [{'produto_id': 6, 'quantidade': '2.000'}, ...]
Sessão só guarda o que é JSON — por isso Decimal vira str ao entrar
e volta a Decimal ao sair.
"""
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    AdicionarItemForm, AdicionarLoteForm,
    FinalizarEntradaForm, FinalizarVendaForm,
    FornecedorForm, ProdutoForm,
)
from .models import Entrada, Fornecedor, ItemVenda, Lote, Produto, Venda
from .perfis import PERFIS, nivel_de
from .services import baixar_estoque_fefo


def perfil_requerido(*permitidos):
    """Exige login E que o nível do usuário esteja na lista.

    Sem nível cadastrado, mostra a página explicando a quem pedir; com
    nível errado, devolve para a tela inicial dele com um aviso — nunca
    um erro seco."""
    def decorador(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            nivel = nivel_de(request.user)
            if nivel is None:
                return render(request, 'core/sem_acesso.html', status=403)
            if nivel not in permitidos:
                nomes = ' ou '.join(PERFIS[p]['nome'] for p in permitidos)
                messages.error(
                    request,
                    f'Esta tela é do nível {nomes} — seu acesso é {PERFIS[nivel]["nome"]}.'
                )
                return redirect(PERFIS[nivel]['inicio'])
            return view(request, *args, **kwargs)
        return login_required(wrapper)
    return decorador


@login_required
def inicio(request):
    """Raiz do site: cada um cai na tela inicial do seu nível."""
    nivel = nivel_de(request.user)
    if nivel is None:
        return render(request, 'core/sem_acesso.html', status=403)
    return redirect(PERFIS[nivel]['inicio'])


def _linhas_do_carrinho(session):
    """Converte o carrinho cru da sessão em linhas prontas para o template."""
    carrinho = session.get('carrinho', [])
    produtos = Produto.objects.in_bulk([c['produto_id'] for c in carrinho])
    linhas, total = [], Decimal('0')
    for indice, c in enumerate(carrinho):
        produto = produtos[c['produto_id']]
        quantidade = Decimal(c['quantidade'])
        subtotal = (quantidade * produto.preco_venda).quantize(Decimal('0.01'))
        linhas.append({'indice': indice, 'produto': produto, 'quantidade': quantidade, 'subtotal': subtotal})
        total += subtotal
    return linhas, total


def _render_caixa(request, form_item=None, form_fim=None):
    linhas, total = _linhas_do_carrinho(request.session)
    return render(request, 'core/caixa.html', {
        'form_item': form_item or AdicionarItemForm(),
        'form_fim': form_fim or FinalizarVendaForm(),
        'linhas': linhas,
        'total': total,
        'produtos_datalist': Produto.objects.filter(ativo=True).values_list('nome', flat=True),
        'aba': 'caixa',
    })


@perfil_requerido('caixa', 'gerente')
def caixa(request):
    return _render_caixa(request)


@perfil_requerido('caixa', 'gerente')
@require_POST
def adicionar_item(request):
    form = AdicionarItemForm(request.POST)
    if not form.is_valid():
        return _render_caixa(request, form_item=form)

    produto = form.cleaned_data['produto']
    quantidade = form.cleaned_data['quantidade']
    carrinho = request.session.get('carrinho', [])

    # mesmo produto duas vezes? soma na linha existente em vez de duplicar
    for c in carrinho:
        if c['produto_id'] == produto.pk:
            c['quantidade'] = str(Decimal(c['quantidade']) + quantidade)
            break
    else:
        carrinho.append({'produto_id': produto.pk, 'quantidade': str(quantidade)})

    request.session['carrinho'] = carrinho  # reatribuir marca a sessão como suja
    return redirect('caixa')


@perfil_requerido('caixa', 'gerente')
@require_POST
def remover_item(request, indice):
    carrinho = request.session.get('carrinho', [])
    if 0 <= indice < len(carrinho):
        carrinho.pop(indice)
        request.session['carrinho'] = carrinho
    return redirect('caixa')


@perfil_requerido('caixa', 'gerente')
@require_POST
def finalizar_venda(request):
    carrinho = request.session.get('carrinho', [])
    if not carrinho:
        messages.error(request, 'Carrinho vazio — adicione ao menos um item.')
        return redirect('caixa')

    form = FinalizarVendaForm(request.POST)
    if not form.is_valid():
        return _render_caixa(request, form_fim=form)

    with transaction.atomic():
        venda = Venda.objects.create(forma_pagamento=form.cleaned_data['forma_pagamento'])
        for c in carrinho:
            item = ItemVenda.objects.create(
                venda=venda,
                produto_id=c['produto_id'],
                quantidade=Decimal(c['quantidade']),
            )
            baixar_estoque_fefo(item)

    del request.session['carrinho']
    return redirect('venda_concluida', pk=venda.pk)


@perfil_requerido('caixa', 'gerente')
def venda_concluida(request, pk):
    venda = get_object_or_404(Venda.objects.prefetch_related('itens__produto'), pk=pk)
    return render(request, 'core/venda_concluida.html', {'venda': venda})


# ---------------------------------------------------------------------------
# Entrada de mercadoria — mesmo padrão do caixa: acumula na sessão,
# banco só é tocado no finalizar. Diferença deliberada: linhas do mesmo
# produto NÃO se mesclam, porque dois lotes do mesmo produto com validades
# diferentes são legítimos — é a razão de Lote existir.
# ---------------------------------------------------------------------------

def _linhas_da_entrada(session):
    itens = session.get('entrada_itens', [])
    produtos = Produto.objects.in_bulk([i['produto_id'] for i in itens])
    linhas, total = [], Decimal('0')
    for indice, i in enumerate(itens):
        quantidade = Decimal(i['quantidade'])
        custo = Decimal(i['custo'])
        subtotal = (quantidade * custo).quantize(Decimal('0.01'))
        linhas.append({
            'indice': indice,
            'produto': produtos[i['produto_id']],
            'quantidade': quantidade,
            'custo': custo,
            'validade': i['validade'] or None,
            'numero_lote': i['numero_lote'],
            'subtotal': subtotal,
        })
        total += subtotal
    return linhas, total


def _render_entrada(request, form_lote=None, form_fim=None):
    linhas, total = _linhas_da_entrada(request.session)
    return render(request, 'core/entrada.html', {
        'form_lote': form_lote or AdicionarLoteForm(),
        'form_fim': form_fim or FinalizarEntradaForm(),
        'linhas': linhas,
        'total': total,
        'produtos_datalist': Produto.objects.filter(ativo=True).values_list('nome', flat=True),
        'aba': 'entrada',
    })


@perfil_requerido('estoque', 'gerente')
def entrada_mercadoria(request):
    return _render_entrada(request)


@perfil_requerido('estoque', 'gerente')
@require_POST
def adicionar_lote(request):
    form = AdicionarLoteForm(request.POST)
    if not form.is_valid():
        return _render_entrada(request, form_lote=form)

    d = form.cleaned_data
    itens = request.session.get('entrada_itens', [])
    itens.append({
        'produto_id': d['produto'].pk,
        'quantidade': str(d['quantidade']),
        'custo': str(d['custo_unitario']),
        'validade': d['validade'].isoformat() if d['validade'] else '',
        'numero_lote': d['numero_lote'] or '',
    })
    request.session['entrada_itens'] = itens
    return redirect('entrada')


@perfil_requerido('estoque', 'gerente')
@require_POST
def remover_lote(request, indice):
    itens = request.session.get('entrada_itens', [])
    if 0 <= indice < len(itens):
        itens.pop(indice)
        request.session['entrada_itens'] = itens
    return redirect('entrada')


@perfil_requerido('estoque', 'gerente')
@require_POST
def finalizar_entrada(request):
    itens = request.session.get('entrada_itens', [])
    if not itens:
        messages.error(request, 'Nenhum lote registrado — adicione ao menos um.')
        return redirect('entrada')

    form = FinalizarEntradaForm(request.POST)
    if not form.is_valid():
        return _render_entrada(request, form_fim=form)

    with transaction.atomic():
        entrada = Entrada.objects.create(
            fornecedor=form.cleaned_data['fornecedor'],
            observacao=form.cleaned_data['observacao'],
        )
        for i in itens:
            lote = Lote(
                entrada=entrada,
                produto_id=i['produto_id'],
                quantidade_inicial=Decimal(i['quantidade']),
                custo_unitario=Decimal(i['custo']),
                validade=i['validade'] or None,
                numero_lote=i['numero_lote'],
            )
            lote.save()  # o save() do modelo copia quantidade_inicial -> quantidade_atual
            # memória de custo: o produto lembra quanto custou da última vez
            Produto.objects.filter(pk=i['produto_id']).update(
                ultimo_custo=Decimal(i['custo'])
            )

    del request.session['entrada_itens']
    return redirect('entrada_concluida', pk=entrada.pk)


@perfil_requerido('estoque', 'gerente')
def entrada_concluida(request, pk):
    entrada = get_object_or_404(
        Entrada.objects.prefetch_related('lotes__produto'), pk=pk
    )
    return render(request, 'core/entrada_concluida.html', {'entrada': entrada})


# ---------------------------------------------------------------------------
# Cadastros: produto e fornecedor. Um único padrão para criar E editar —
# a mesma view serve as duas, mudando só o `instance` do ModelForm.
# ---------------------------------------------------------------------------

def _tela_cadastro(request, *, form_cls, template, contexto_lista, url_ok, instancia=None):
    """Esqueleto comum de cadastro: GET mostra, POST valida-salva-redireciona."""
    if request.method == 'POST':
        form = form_cls(request.POST, instance=instancia)
        if form.is_valid():
            objeto = form.save()
            verbo = 'atualizado' if instancia else 'cadastrado'
            messages.success(request, f'{objeto} {verbo}.')
            return redirect(url_ok)
    else:
        form = form_cls(instance=instancia)
    return render(request, template, {**contexto_lista(), 'form': form, 'editando': instancia})


@perfil_requerido('estoque', 'gerente')
def produtos(request, pk=None):
    instancia = get_object_or_404(Produto, pk=pk) if pk else None
    return _tela_cadastro(
        request,
        form_cls=ProdutoForm,
        template='core/produtos.html',
        contexto_lista=lambda: {'produtos': Produto.objects.all(), 'aba': 'produtos'},
        url_ok='produtos',
        instancia=instancia,
    )


@perfil_requerido('estoque', 'gerente')
def fornecedores(request, pk=None):
    instancia = get_object_or_404(Fornecedor, pk=pk) if pk else None
    return _tela_cadastro(
        request,
        form_cls=FornecedorForm,
        template='core/fornecedores.html',
        contexto_lista=lambda: {'fornecedores': Fornecedor.objects.all(), 'aba': 'fornecedores'},
        url_ok='fornecedores',
        instancia=instancia,
    )
