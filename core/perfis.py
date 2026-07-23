"""Perfis de operação: depois do login, quem está no balcão escolhe o seu.

Um perfil não é um usuário — é um modo de trabalho guardado na sessão do
navegador. Todos compartilham o mesmo login; o perfil decide quais telas
aparecem no menu, onde a pessoa começa e o que o servidor deixa acessar.
Troca de perfil é livre (tela /perfil/) — é organização do trabalho,
não barreira de segurança entre funcionários.
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
