# mercado

Sistema de caixa e controle de estoque para um mercado de bairro. Django +
SQLite, uma única app (`core`), pensado para rodar numa máquina só ou num
plano gratuito de hospedagem.

Duas telas cobrem o dia a dia de quem opera o balcão:

- **`/caixa/`** — vender: busca produto por nome ou código de barras, monta
  o carrinho, finaliza com forma de pagamento.
- **`/entrada/`** — receber mercadoria: registra o que chegou (produto,
  quantidade, custo, validade), criando um lote de estoque por linha.

E dois cadastros de apoio:

- **`/produtos/`** — catálogo (nome, categoria, preço, estoque mínimo etc.)
- **`/fornecedores/`** — fornecedores

O `/admin/` do Django cobre o que essas telas não cobrem: consultar lotes
por vencimento, ver o total de estoque de cada produto contra o mínimo,
lançar **ajustes** de estoque (perda, quebra, consumo interno, acerto de
contagem) e **criar os logins** dos funcionários. O login do sistema tem
tela própria em `/entrar/`.

## Início rápido (local)

```bash
git clone <url-do-repositorio> mercado
cd mercado
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abra `http://127.0.0.1:8000/` e entre — cada usuário cai na tela do seu
nível de acesso. Cadastre ao menos um produto em `/produtos/` antes de
tentar vender — o caixa não cria produto.

Requer Python ≥ 3.12 para produção (Django 6 exige; localmente o projeto
também roda em 3.10/3.13 — veja `requirements.txt`).

## Configuração

Tudo por variável de ambiente; sem elas, o projeto usa padrões de
desenvolvimento (`config/settings.py`):

| Variável | Padrão (dev) | Produção |
|---|---|---|
| `DJANGO_SECRET_KEY` | chave fixa de dev | gerar uma nova, nunca commitar |
| `DJANGO_DEBUG` | `1` | `0` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | domínio real, ex. `seunome.pythonanywhere.com` |

Passo a passo completo de deploy (PythonAnywhere, backup do banco, limites
do plano gratuito): ver [`DEPLOY.md`](./DEPLOY.md).

## Níveis de acesso

Cada funcionário tem seu login (usuário + senha) com um **nível de
acesso**, gravado no modelo `Funcionario`. O menu e as telas se adaptam
ao nível de quem entrou — e o servidor bloqueia o resto:

| Nível | Vê |
|---|---|
| Caixa | só o caixa |
| Estoque | entrada, produtos, fornecedores |
| Gerente | tudo, incluindo o `/admin/` |

Depois do login, todos caem na **tela inicial** (`/`), que mostra um
botão para cada área disponível àquele nível — o logotipo MERCADO no
menu volta para ela de qualquer tela.

Quem cria e edita logins é o gerente, em **`/admin/` → Usuários** — o
nível de acesso aparece dentro da própria tela do usuário. Superusuário
sem nível cadastrado conta como gerente; usuário comum sem nível não
acessa nada até o gerente definir. A senha fica na tabela de usuários
do Django, criptografada — nunca em texto puro.

A instalação cria três logins de exemplo (`adm`/`adm` gerente,
`estoque`/`estoque`, `caixa`/`caixa`) — **troque as senhas** assim que o
sistema estiver em uso real: `python manage.py changepassword adm` etc.

## Uso do dia a dia

Fluxo típico de um produto novo:

1. Cadastrar o produto em `/produtos/` (preço, categoria, se é perecível).
2. Registrar a entrada da mercadoria em `/entrada/` — isso cria o(s) lote(s)
   de estoque e grava o custo em `Produto.ultimo_custo`.
3. Vender em `/caixa/` — a baixa de estoque escolhe automaticamente o lote
   que vence primeiro (FEFO). Se não houver lote suficiente, a venda **não
   é bloqueada**: a diferença fica registrada como discrepância a
   investigar (`quantidade_sem_lote`), visível no admin em cada item de
   venda.
4. Perdas, quebras, consumo interno ou correções de contagem: lançar um
   **Ajuste** pelo `/admin/` (não tem tela própria). Ajuste é lançamento
   único — depois de criado, não se edita nem se apaga.

Detalhes de por que o sistema funciona assim estão em
[`ARCHITECTURE.md`](./ARCHITECTURE.md).

## Usando no iPhone/iPad (e Android)

O sistema é um site responsivo e roda inteiro no navegador — não há app
nas lojas, e não precisa: dá para **instalá-lo na tela de início**, onde
abre em tela cheia como um app (PWA).

No iPhone/iPad, com o site já no ar (ver `DEPLOY.md`):

1. Abra `https://SEUNOME.pythonanywhere.com/caixa/` no **Safari**
   (precisa ser o Safari — outros navegadores no iOS não instalam).
2. Faça login.
3. Toque no botão **Compartilhar** (quadrado com seta para cima) →
   **Adicionar à Tela de Início** → **Adicionar**.

Aparece o ícone "Mercado" na tela de início; ele abre direto no caixa,
sem a barra do navegador. No Android (Chrome) é o menu ⋮ →
**Adicionar à tela inicial**.

O login vale por duas semanas (sessão padrão do Django); depois disso o
app pede login de novo. Os arquivos do PWA vivem em `core/static/core/`
(`manifest.json` + ícones) e as meta tags no `core/templates/core/base.html`.

## Estrutura do projeto

```
config/     settings, urls, wsgi/asgi (padrão startproject)
core/       toda a aplicação
  models.py    Produto, Fornecedor, Entrada, Lote, Ajuste, Venda, ItemVenda, BaixaLote
  perfis.py    perfis de operação (caixa/estoque/gerente) e o que cada um vê
  forms.py     formulários do caixa e da entrada (não são ModelForm)
  services.py  baixar_estoque_fefo — a única regra que atravessa vários modelos
  views.py     caixa, entrada, cadastros
  admin.py     inspeção de estoque, ajustes, filtros de vencimento
  templates/   core/*.html
db.sqlite3  banco (fora do git — ver .gitignore)
```

## Testes

```bash
python manage.py test
```

`core/tests.py` ainda está vazio — é o próximo débito óbvio, dado que
`services.baixar_estoque_fefo` concentra a lógica mais delicada do sistema.
