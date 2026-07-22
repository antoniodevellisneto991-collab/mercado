# Arquitetura

## Contexto e objetivos

Sistema para um único mercado, operado por gente não-técnica no balcão
(caixa e recebimento de mercadoria). As prioridades que moldam as decisões
abaixo:

- **Rastreabilidade de estoque por lote** — cada recebimento de mercadoria
  tem seu próprio custo e validade, mesmo quando é o mesmo produto.
- **A venda nunca trava** — falta de estoque vira discrepância registrada,
  não um erro que impede o operador de fechar a venda.
- **Deploy trivial** — SQLite (um arquivo), sem serviços externos. Ver
  [`DEPLOY.md`](./DEPLOY.md).

## Estrutura

```
config/    settings, urls, wsgi/asgi — padrão startproject, sem lógica própria
core/      única app Django: models, forms, views, services, admin, templates
```

Não há API separada (REST/DRF): o sistema é só views + templates Django.

## Modelo de dados

```
Fornecedor ──< Entrada ──< Lote >── Produto
                              │
                              └──< BaixaLote >── ItemVenda >── Venda

Lote ──< Ajuste
```

- **Produto** — catálogo. Não guarda quantidade — isso é responsabilidade
  de `Lote`. Guarda `preco_venda` (preço corrente) e `ultimo_custo`
  (informativo, atualizado a cada entrada).
- **Fornecedor** — cadastro simples, ligado a `Entrada` por FK opcional.
- **Entrada** — um recebimento de mercadoria; agrupa um ou mais `Lote`.
- **Lote** — a unidade real de estoque: quanto entrou
  (`quantidade_inicial`), quanto resta (`quantidade_atual`), a que custo e
  até quando. Ordenado por validade (nulos por último) — é a base do FEFO.
- **Ajuste** — correção manual assinada num lote (perda, quebra, consumo,
  acerto de contagem). Livro-razão: só entra, nunca muda ou some.
- **Venda** — uma passagem pelo caixa; agrupa `ItemVenda`.
- **ItemVenda** — uma linha vendida. `preco_unitario` é copiado de
  `Produto.preco_venda` no momento da venda (congelado). `quantidade_sem_lote`
  guarda o que não foi coberto por nenhum lote.
- **BaixaLote** — trilha de auditoria: qual lote cobriu qual item de venda,
  e quanto. Sem isso, o sistema saberia que o estoque caiu, mas não de onde
  saiu.

## Decisões e por quês

**Lote separado de Produto.** Produto é catálogo; Lote é estoque. Isso
permite dois lotes do mesmo produto com validades e custos diferentes
coexistindo — é literalmente a razão de `Lote` existir como modelo à parte
(ver docstring de `Entrada` em `models.py`).

**Baixa de estoque por FEFO, sem bloquear a venda.**
`core/services.py::baixar_estoque_fefo` percorre os lotes do produto com
saldo, do vencimento mais próximo para o mais distante, descontando até
cobrir a quantidade vendida. Usa `select_for_update()` dentro de
`transaction.atomic` para não haver corrida entre duas vendas simultâneas
do mesmo produto. O que não couber em lote nenhum vira
`item.quantidade_sem_lote` — a venda é registrada de qualquer forma; a
diferença fica visível no admin (`ItemVendaInline.cobertura`) como algo a
investigar, não como erro fatal.

**Preço congelado em ItemVenda.** `preco_unitario` é copiado de
`Produto.preco_venda` no `save()` do item, não é uma referência viva. Se o
preço do produto mudar amanhã, o histórico de vendas passadas não muda
junto.

**Ajuste como livro-razão.** `Ajuste.save()` aplica seu efeito em
`Lote.quantidade_atual` só na criação, dentro de uma transação; `clean()`
impede que o ajuste deixe o saldo negativo. O admin reforça isso
desabilitando change/delete (`AjusteAdmin.has_change_permission` /
`has_delete_permission`). Corrigir um ajuste errado significa lançar outro
ajuste, não editar o histórico.

**Carrinho e entrada em construção vivem na sessão, não no banco.**
Em `/caixa/` e `/entrada/`, cada item adicionado fica na sessão do
navegador (lista de dicts JSON — por isso `Decimal` vira `str` na ida e
volta). O banco só é tocado em `finalizar_venda` / `finalizar_entrada`,
dentro de uma única transação atômica que cria `Venda`/`Entrada` e todos
os itens/lotes de uma vez. Consequência prática: desistir no meio de uma
venda não deixa registro órfão no banco.

Diferença deliberada entre os dois fluxos: no caixa, adicionar o mesmo
produto duas vezes soma na mesma linha; na entrada, linhas do mesmo
produto **não** se mesclam — dois lotes do mesmo produto com validades
diferentes são legítimos (comentário em `views.py`).

**Login reaproveitado do admin.** Não há tela de login própria;
`LOGIN_URL = '/admin/login/'` e todas as views do `core` usam
`@login_required(login_url=LOGIN_URL)`.

**Admin como "tela avançada".** Filtros que não existem nas telas do
caixa moram no admin: `VencimentoFilter` (lotes vencidos / a vencer em
7/15/30 dias) e `EstoqueFilter` (produtos abaixo do mínimo, zerados, ok) —
este último depende de uma anotação (`Sum` + `Coalesce`) feita em
`ProdutoAdmin.get_queryset`. Ajustes e a consulta de fornecedores também
só têm tela no admin (fornecedores tem view própria em `/fornecedores/`
*e* está registrado no admin).

**Configuração por variável de ambiente.** `DJANGO_SECRET_KEY`,
`DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` — o mesmo código roda em
desenvolvimento (padrões embutidos) e produção (variáveis definidas no
servidor), sem branch de ambiente no código.

**SQLite + WhiteNoise + Gunicorn.** Banco em um único arquivo
(`db.sqlite3`) — backup é copiar um arquivo, sem servidor de banco
separado para operar. WhiteNoise serve os estáticos dentro do próprio
processo Django, sem depender de um servidor de arquivos externo. Detalhes
operacionais (backup, hibernação no plano gratuito, caminho de migração
para VPS) estão em [`DEPLOY.md`](./DEPLOY.md), não repetidos aqui.

## Fluxo de dados: uma venda

1. Operador busca produto em `/caixa/` → `AdicionarItemForm` resolve o
   termo (código de barras exato → nome exato → nome parcial único) →
   linha entra na sessão.
2. `finalizar_venda`: dentro de uma transação, cria `Venda`, depois um
   `ItemVenda` por linha da sessão.
3. Para cada `ItemVenda`, `baixar_estoque_fefo` desconta lote(s) por
   validade, criando um `BaixaLote` por lote tocado; sobra vira
   `quantidade_sem_lote`.
4. Sessão do carrinho é limpa; operador vai para a tela de venda
   concluída.

## Fluxo de dados: uma entrada de mercadoria

1. Operador adiciona linhas em `/entrada/` (produto, quantidade, custo,
   validade — obrigatória se o produto for perecível) → sessão.
2. `finalizar_entrada`: dentro de uma transação, cria `Entrada` e um
   `Lote` por linha; `Lote.save()` inicializa `quantidade_atual` a partir
   de `quantidade_inicial`.
3. `Produto.ultimo_custo` é atualizado para cada produto recebido.

## Débitos conhecidos

- `core/tests.py` está vazio. `baixar_estoque_fefo` é a lógica mais
  sensível do sistema (concorrência, FEFO, discrepância) e não tem
  cobertura automatizada.
- Não existe tela própria para lançar `Ajuste` fora do admin — aceitável
  hoje porque só o superusuário mexe nisso, mas vale revisar se o
  funcionário do caixa passar a precisar lançar perdas direto.
