# Despliegue en Ubuntu Server

Esta guía describe cómo publicar eGraduados con **gunicorn + systemd + Nginx**
detrás de HTTPS. El desarrollo en Windows sigue usando `runserver` y un `.env`
local (ver `.env.example`).

## 1. Preparar el servidor

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev default-libmysqlclient-dev \
    build-essential pkg-config nginx mysql-client git
```

`mysqlclient` necesita esos headers para compilarse.

## 2. Instalar el proyecto

```bash
sudo mkdir -p /srv/egraduados
sudo chown $USER:$USER /srv/egraduados
cd /srv/egraduados
git clone <url-del-repositorio> B-Codigo
cd B-Codigo
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 3. Base de datos

```sql
CREATE DATABASE egraduados CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'egraduados'@'localhost' IDENTIFIED BY '<clave-segura>';
GRANT ALL PRIVILEGES ON egraduados.* TO 'egraduados'@'localhost';
FLUSH PRIVILEGES;
```

## 4. Archivo de configuración

```bash
cp .env.example .env
nano .env
```

Completar al menos:

- `DJANGO_DEBUG=0`
- `DJANGO_SECRET_KEY`: generar uno nuevo:
  ```bash
  python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
  ```
- `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS` con el dominio real
  (el origen CSRF debe incluir `https://`).
- `DJANGO_DB_*` con los datos creados arriba.
- `DJANGO_EMAIL_*` con el SMTP real.

El archivo debe ser legible por el usuario del servicio:

```bash
sudo chown root:www-data /srv/egraduados/B-Codigo/.env
sudo chmod 640 /srv/egraduados/B-Codigo/.env
```

> No usar `export` ni espacios alrededor del `=`. Si una clave contiene `#`,
> comillas u otros caracteres especiales, citar todo el valor. `.env` está
> ignorado por Git: **nunca subirlo al repositorio**.

Las variables inyectadas por systemd (`EnvironmentFile`) tienen prioridad
sobre el archivo porque Django usa `load_dotenv(..., override=False)`.

## 5. Migraciones y datos iniciales

```bash
cd /srv/egraduados/B-Codigo
source venv/bin/activate

python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py crear_usuario_admin --email admin@gmail.com --nombre "Administrador"
python manage.py recalcular_promedios
```

`recalcular_promedios` se ejecuta **una sola vez** después de migrar: completa
los promedios que estaban importados del Excel. Respeta los promedios manuales;
para simularlo antes, agregar `--dry-run`.

## 6. Servicio systemd

`/etc/systemd/system/egraduados.service`:

```ini
[Unit]
Description=eGraduados (gunicorn)
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/srv/egraduados/B-Codigo
EnvironmentFile=/srv/egraduados/B-Codigo/.env
ExecStart=/srv/egraduados/B-Codigo/venv/bin/gunicorn egraduados_core.wsgi:application \
    --bind 127.0.0.1:8000 --workers 3 \
    --access-logfile /var/log/egraduados/access.log \
    --error-logfile /var/log/egraduados/error.log
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo mkdir -p /var/log/egraduados
sudo chown www-data:www-data /var/log/egraduados
sudo systemctl daemon-reload
sudo systemctl enable --now egraduados
sudo systemctl status egraduados
```

Cada vez que cambie `.env` o el código: `sudo systemctl restart egraduados`.

## 7. Nginx (proxy TLS y estáticos)

```nginx
server {
    listen 80;
    server_name egraduados.unpa.edu.ar;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name egraduados.unpa.edu.ar;

    ssl_certificate     /etc/ssl/certs/egraduados.crt;
    ssl_certificate_key /etc/ssl/private/egraduados.key;

    client_max_body_size 10m;   # igual a DJANGO_MAX_UPLOAD_SIZE

    location /static/ {
        alias /srv/egraduados/B-Codigo/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

`X-Forwarded-Proto` es necesario: `settings.py` ya define
`SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`.

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## 8. Verificación final

- `python manage.py check --deploy` sin avisos.
- Ingresar con el usuario creado, cargar un analítico, validarlo y descargar el `.docx`.
- Confirmar que el admin de Django no queda expuesto (`DJANGO_HABILITAR_ADMIN=0`).
- Revisar `/var/log/egraduados/error.log` tras la primera carga real.

## Actualizaciones posteriores

```bash
cd /srv/egraduados/B-Codigo
git pull
source venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart egraduados
```
