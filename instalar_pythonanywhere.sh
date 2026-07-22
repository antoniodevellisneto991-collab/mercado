#!/bin/bash
# Instala o sistema numa conta do PythonAnywhere.
#
# Como usar: crie a conta gratuita em pythonanywhere.com, abra um console
# Bash (menu Consoles -> Bash) e cole UMA linha:
#
#   bash <(curl -sL https://raw.githubusercontent.com/antoniodevellisneto991-collab/mercado/main/instalar_pythonanywhere.sh)
#
# O script clona o projeto, instala as dependências, cria o banco com o
# usuário adm/adm e imprime, já preenchido, tudo o que falta colar na
# aba Web (virtualenv, WSGI e estáticos).
set -e

REPO=https://github.com/antoniodevellisneto991-collab/mercado.git

# Django 6 exige Python >= 3.12; contas novas do PythonAnywhere têm 3.13
PY=''
for v in 3.13 3.12; do
    if command -v python$v >/dev/null 2>&1; then PY=python$v; break; fi
done
if [ -z "$PY" ]; then
    echo 'ERRO: esta conta não tem Python 3.12 ou mais novo.'
    echo 'Contas criadas recentemente têm — confira em: python3 --version'
    exit 1
fi

cd ~
[ -d mercado ] || git clone "$REPO"
cd mercado
git pull --ff-only || true

[ -d .venv ] || $PY -m venv .venv
source .venv/bin/activate
pip install --quiet -r requirements.txt

python manage.py migrate --noinput
python manage.py collectstatic --noinput >/dev/null

# usuário inicial do sistema (trocar a senha depois do primeiro acesso!)
python manage.py shell -c "
from django.contrib.auth.models import User
u, _ = User.objects.get_or_create(username='adm')
u.is_staff = True
u.is_superuser = True
u.set_password('adm')
u.save()
"

# chave sem caracteres especiais de shell, segura para colar entre aspas
KEY=$(python -c "
from django.utils.crypto import get_random_string
print(get_random_string(50, 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'))
")
PYV=$($PY -c 'import sys; print("%d.%d" % sys.version_info[:2])')

cat <<FIM

======================================================================
 INSTALACAO CONCLUIDA — falta so a aba Web (2 minutos):
======================================================================

 1) Menu Web -> Add a new web app -> Next
    -> Manual configuration -> Python $PYV -> Next

 2) Secao "Virtualenv": cole o caminho abaixo e confirme:

      /home/$USER/mercado/.venv

 3) Secao "Code": clique no link do "WSGI configuration file",
    APAGUE TUDO que estiver la e cole o bloco abaixo, sem mudar nada:

----------------------------------------------------------------------
import os
import sys

sys.path.insert(0, '/home/$USER/mercado')

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DJANGO_DEBUG'] = '0'
os.environ['DJANGO_ALLOWED_HOSTS'] = '$USER.pythonanywhere.com'
os.environ['DJANGO_SECRET_KEY'] = '$KEY'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
----------------------------------------------------------------------

 4) Secao "Static files", adicione uma linha:
      URL: /static/      Directory: /home/$USER/mercado/staticfiles

 5) Clique no botao verde "Reload".

 O sistema estara no ar em:

      https://$USER.pythonanywhere.com/caixa/

 Login: adm   Senha: adm
 (troque a senha depois: python manage.py changepassword adm)
======================================================================
FIM
