"""Deixa o perfil da sessão disponível em todo template (o base.html monta
o menu a partir dele, sem que cada view precise repassar)."""
from .perfis import PERFIS


def perfil(request):
    info = PERFIS.get(request.session.get('perfil'))
    if info is None:
        return {'perfil_nome': None, 'abas_perfil': (), 'perfil_admin': False}
    return {
        'perfil_nome': info['nome'],
        'abas_perfil': info['abas'],
        'perfil_admin': info['admin'],
    }
