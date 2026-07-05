# Colocando o sistema online — PythonAnywhere

Roteiro para o plano **gratuito** (endereço `SEUNOME.pythonanywhere.com`).
Reserve ~1 hora na primeira vez.

## 0. Antes de subir (na sua máquina)

```bash
cd ~/mercado
source .venv/bin/activate
pip install -r requirements.txt          # instala whitenoise e gunicorn
python manage.py check                   # deve passar limpo
```

Gere uma SECRET_KEY nova (a do código é só de desenvolvimento):

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Guarde essa chave — vai para o servidor, nunca para o código.

## 1. Conta e código

1. Crie a conta gratuita em https://www.pythonanywhere.com
2. Abra um **Bash console** (menu Consoles) e envie o projeto.
   O caminho mais simples é via git (crie um repositório privado no GitHub):

   ```bash
   git clone https://github.com/SEU_USUARIO/mercado.git
   ```

   Alternativa sem git: zip do projeto + upload na aba Files + `unzip`.
   **Não inclua** `.venv/` nem `db.sqlite3` de teste — mas LEVE o
   `db.sqlite3` real se quiser começar com os dados atuais.

## 2. Ambiente virtual no servidor

No mesmo console Bash:

```bash
cd ~/mercado
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py collectstatic --noinput
```

## 3. Web app

1. Aba **Web** → *Add a new web app* → **Manual configuration** → Python 3.11
2. Em **Virtualenv**, informe: `/home/SEUNOME/mercado/.venv`
3. Em **Code → WSGI configuration file**, clique e substitua o conteúdo por:

   ```python
   import os
   import sys

   sys.path.insert(0, '/home/SEUNOME/mercado')

   os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
   os.environ['DJANGO_DEBUG'] = '0'
   os.environ['DJANGO_ALLOWED_HOSTS'] = 'SEUNOME.pythonanywhere.com'
   os.environ['DJANGO_SECRET_KEY'] = 'COLE-AQUI-A-CHAVE-GERADA-NO-PASSO-0'

   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```

4. Em **Static files**, adicione:
   - URL: `/static/`  →  Directory: `/home/SEUNOME/mercado/staticfiles`
5. Botão verde **Reload**.

Pronto: `https://SEUNOME.pythonanywhere.com/caixa/`

## 4. Usuários

No console Bash do servidor:

```bash
cd ~/mercado && source .venv/bin/activate
python manage.py migrate
python manage.py createsuperuser   # se não levou o db.sqlite3 com usuários
```

Sistema na internet = senha forte. Uma para você (superuser),
outra para o funcionário (crie no /admin/ um usuário staff sem
permissão de apagar).

## 5. Backup (inegociável)

O banco é UM arquivo: `/home/SEUNOME/mercado/db.sqlite3`.

- Rotina mínima: aba **Files** → baixar o `db.sqlite3` toda semana.
- Rotina melhor: aba **Tasks** (1 tarefa agendada no plano free), diária:

  ```bash
  cp ~/mercado/db.sqlite3 ~/backup_$(date +\%u).sqlite3
  ```

  (mantém 7 cópias rotativas, uma por dia da semana — some com o
  problema de "sobrescrevi o backup com o banco já corrompido")

## 6. Limites do plano gratuito

- Endereço fixo `SEUNOME.pythonanywhere.com` (domínio próprio só no pago, US$5/mês)
- Uma web app, CPU limitada — suficiente para um mercadinho
- A app **hiberna se ninguém clicar em "Run until 3 months from today"**
  na aba Web a cada 3 meses — anote na agenda

## Se um dia migrar para VPS (Hetzner etc.)

O projeto já está pronto: `gunicorn config.wsgi` + nginx na frente +
as mesmas variáveis de ambiente. Nada no código muda.
