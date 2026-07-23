"""Níveis de acesso: cada login tem o seu, gravado em Funcionario.

O nível vem da conta de quem entrou (não é mais escolha livre na sessão):
decide quais telas aparecem no menu, onde a pessoa começa e o que o
servidor deixa acessar. Quem administra os logins é o gerente, pelo /admin/.
"""

# O que cada área do sistema é — a tela inicial monta seus botões daqui.
ABAS = {
    'caixa': {'nome': 'Caixa', 'url': 'caixa', 'descricao': 'vender no balcão'},
    'entrada': {'nome': 'Entrada', 'url': 'entrada', 'descricao': 'receber mercadoria'},
    'produtos': {'nome': 'Produtos', 'url': 'produtos', 'descricao': 'catálogo e preços'},
    'fornecedores': {'nome': 'Fornecedores', 'url': 'fornecedores', 'descricao': 'de quem se compra'},
}

PERFIS = {
    'caixa': {
        'nome': 'Caixa',
        'abas': ['caixa'],
        'admin': False,
    },
    'estoque': {
        'nome': 'Estoque',
        'abas': ['entrada', 'produtos', 'fornecedores'],
        'admin': False,
    },
    'gerente': {
        'nome': 'Gerente',
        'abas': ['caixa', 'entrada', 'produtos', 'fornecedores'],
        'admin': True,
    },
}


def nivel_de(user):
    """Nível de acesso de um usuário logado, ou None.

    A regra: o que vale é o registro Funcionario. Superusuário sem registro
    conta como gerente (senão o dono se trancaria para fora do próprio
    sistema). Usuário comum sem registro não tem acesso nenhum.
    """
    if not user.is_authenticated:
        return None
    funcionario = getattr(user, 'funcionario', None)  # OneToOne ausente vira None
    if funcionario is not None:
        return funcionario.nivel
    if user.is_superuser:
        return 'gerente'
    return None
