"""Deixa o nível de acesso do usuário logado disponível em todo template
(o base.html monta o menu a partir dele, sem que cada view precise repassar)."""
from .perfis import PERFIS, nivel_de


def perfil(request):
    info = PERFIS.get(nivel_de(request.user))
    if info is None:
        return {'perfil_nome': None, 'abas_perfil': (), 'perfil_admin': False}
    return {
        'perfil_nome': info['nome'],
        'abas_perfil': info['abas'],
        'perfil_admin': info['admin'],
    }
