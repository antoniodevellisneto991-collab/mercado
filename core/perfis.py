"""Níveis de acesso: cada login tem o seu, gravado em Funcionario.

O nível vem da conta de quem entrou (não é mais escolha livre na sessão):
decide quais telas aparecem no menu, onde a pessoa começa e o que o
servidor deixa acessar. Quem administra os logins é o gerente, pelo /admin/.
"""

PERFIS = {
    'caixa': {
        'nome': 'Caixa',
        'descricao': 'vender no balcão',
        'abas': ['caixa'],
        'inicio': 'caixa',
        'admin': False,
    },
    'estoque': {
        'nome': 'Estoque',
        'descricao': 'receber mercadoria e cuidar do catálogo',
        'abas': ['produtos', 'fornecedores', 'entrada'],
        'inicio': 'entrada',
        'admin': False,
    },
    'gerente': {
        'nome': 'Gerente',
        'descricao': 'todas as telas e a administração',
        'abas': ['produtos', 'fornecedores', 'entrada', 'caixa'],
        'inicio': 'caixa',
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
