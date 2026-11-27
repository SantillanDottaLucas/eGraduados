# Despliegue en Ubuntu Server

Esta guía describe cómo publicar eGraduados con **gunicorn + systemd + Nginx**
detrás de HTTPS. El desarrollo en Windows sigue usando `runserver` y un `.env`
local (ver `.env.example`).

La ruta de instalación **no está fijada**: se elige al clonar y se guarda en
`EGRADUADOS_DIR` dentro del `.env`. A partir de ahí,
`scripts/configurar_despliegue.sh` genera el servicio systemd y el virtualhost
de Nginx a partir de las plantillas de `deploy/`.

## 1. Preparar el servidor

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev default-libmysqlclient-dev \
    build-essential pkg-config nginx mysql-client git
```

`mysqlclient` necesita esos headers para compilarse. Si la base de datos va en
el mismo servidor, agregar también `mysql-server`.

**Python 3.13** (el que declara `requirements.txt`). En Ubuntu 24.04 y 26.04
el `python3` del sistema es 3.12 y 3.14 respectivamente, y **no hay paquetes
`python3.13` en los repositorios oficiales**: usar el PPA de deadsnakes
(terceros, fuera del soporte de Canonical).

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev
python3.13 --version
```

No reemplazar `/usr/bin/python3`: las herramientas del sistema dependen del
intérprete por defecto. Django 6.1.1 admite Python ≥ 3.12, pero las versiones
fijadas se probaron con 3.13.

## 2. Instalar el proyecto

Elegir el nombre de la carpeta (acá `egraduados`; puede ser cualquier otro):

```bash
sudo mkdir -p /srv/egraduados
cd /srv/egraduados
git clone <url-del-repositorio> egraduados
cd egraduados
python3.13 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Ese nombre se copia una sola vez a `EGRADUADOS_DIR` en el `.env` (paso 4);
después el script lo usa para todo lo demás.

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

- `EGRADUADOS_DIR`: la ruta absoluta elegida en el paso 2
  (`/srv/egraduados/egraduados` en el ejemplo). Debe coincidir con la carpeta
  donde ejecutás el script: éste lo valida y se niega a generar configs si no
  coincide.
- `DJANGO_DEBUG=0`.
- `DJANGO_SECRET_KEY`: generar uno nuevo:
  ```bash
  python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
  ```
- `DJANGO_ALLOWED_HOSTS`: todos los nombres que debe servir Nginx (separados
  por comas). El script los usa como `server_name`.
- `DJANGO_CSRF_TRUSTED_ORIGINS` con el dominio real (el origen CSRF debe
  incluir `https://`).
- `DJANGO_DB_*` con los datos creados arriba.
- `DJANGO_EMAIL_*` con el SMTP real.

El archivo debe ser legible por el usuario que ejecuta los comandos y por el
usuario del servicio:

```bash
sudo chown "$USER:www-data" .env
sudo chmod 640 .env
```

> No usar `export` ni espacios alrededor del `=`. Si una clave contiene `#`,
> comillas u otros caracteres especiales, citar todo el valor. systemd no
> acepta comentarios al final de una línea. `.env` está ignorado por Git:
> **nunca subirlo al repositorio**.

El `.env` es la única fuente de configuración: Django lo carga siempre con
`load_dotenv(..., override=True)`, incluso en los tests. Por lo tanto, cualquier
variable con el mismo nombre que venga de systemd (`EnvironmentFile`), Docker
o la consola es **ignorada**. Si falta el archivo o una clave obligatoria, el
proyecto no arranca. El motor de la base es MySQL fijo: no se admite SQLite ni
la variable `DJANGO_DB_ENGINE`.

## 5. Migraciones y datos iniciales

```bash
cd /srv/egraduados/egraduados   # la ruta elegida en el paso 2
source venv/bin/activate

python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py crear_usuario_admin
python manage.py recalcular_promedios
```

> También podés pasar `--email` y `--nombre` explícitamente. Sin esos
> argumentos, el comando toma `EGRADUADOS_ADMIN_EMAIL` y
> `EGRADUADOS_ADMIN_NOMBRE` del entorno (o del `.env`). Usá
> `createsuperuser` **sólo** para el admin de Django: no crea el usuario de la
> aplicación, que vive en la tabla `USUARIO` y es necesario para iniciar sesión.
>
> `crear_usuario_admin` muestra el código de acceso de 6 caracteres **una sola
> vez** por consola: copialo, porque no se envía por correo y se guarda hasheado.
> El email debe ser una cuenta `@gmail.com` (es una restricción del modelo de
> usuarios).

`recalcular_promedios` se ejecuta **una sola vez** después de migrar: completa
los promedios que estaban importados del Excel. Respeta los promedios manuales;
para simularlo antes, agregar `--dry-run`.

## 6. Servicio systemd y Nginx

Las definiciones viven en plantillas versionadas:

- `deploy/egraduados.service.tpl`: servicio gunicorn (`www-data`, 3 workers,
  logs en `/var/log/egraduados`).
- `deploy/nginx-egraduados.conf.tpl`: redirección 80 → 443, TLS, estáticos y
  proxy a `127.0.0.1:8000`.

El script rellena `@APP_DIR@` con `EGRADUADOS_DIR` y `@DOMINIOS@` con
`DJANGO_ALLOWED_HOSTS`. Revisar primero el resultado sin escribir nada:

```bash
bash scripts/configurar_despliegue.sh --dry-run
bash scripts/configurar_despliegue.sh
sudo systemctl enable --now egraduados
sudo systemctl status egraduados
```

El script genera:

- `/etc/systemd/system/egraduados.service`
- `/etc/nginx/sites-available/egraduados` (y el symlink en `sites-enabled`)
- `/var/log/egraduados` con propietario `www-data`

Después ejecuta `systemctl daemon-reload` y `nginx -t`.

> systemd permite `${VAR}` en `ExecStart`, pero **no** en `WorkingDirectory=`
> ni en la ruta de `EnvironmentFile=`. Por eso el script escribe las rutas
> literales desde la plantilla; no hace falta editar los archivos generados a
> mano.

Cada vez que cambie `.env` (ruta o dominios) o las plantillas: volver a
ejecutar el script y reiniciar los servicios.

## 7. Certificado TLS

Las plantillas usan:

```
ssl_certificate     /etc/ssl/certs/egraduados.crt;
ssl_certificate_key /etc/ssl/private/egraduados.key;
```

Si los certificados están en otra ubicación (por ejemplo los de Let's
Encrypt), ajustar `deploy/nginx-egraduados.conf.tpl` antes de generar la
configuración. Verificar y recargar:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

`X-Forwarded-Proto` es necesario: `settings.py` ya define
`SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`. El
`client_max_body_size 10m` coincide con `DJANGO_MAX_UPLOAD_SIZE`.

> La app no sirve archivos subidos por URL (los PDF de planes se leen desde
> disco), por lo que no hace falta un `location /media/`. `static(MEDIA_URL, ...)`
> de `urls.py` sólo actúa con `DEBUG=1`.

## 8. Verificación final

- `python manage.py check --deploy` sin avisos.
- Ingresar con el usuario creado y el código impreso en el paso 5; cargar un
  analítico, validarlo y descargar el `.docx`.
- Confirmar que el admin de Django no queda expuesto
  (`DJANGO_HABILITAR_ADMIN=0`).
- Revisar `/var/log/egraduados/error.log` tras la primera carga real.

## 9. Cambiar el nombre de la carpeta

1. Mover el directorio a la nueva ruta.
2. Actualizar `EGRADUADOS_DIR` en el `.env` de la nueva ubicación.
3. Volver a ejecutar `bash scripts/configurar_despliegue.sh` desde la nueva
   carpeta (el script valida que coincida con el directorio actual).
4. `sudo systemctl restart egraduados && sudo systemctl reload nginx`.

## Actualizaciones posteriores

```bash
cd /srv/egraduados/egraduados   # la ruta elegida
git pull
source venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
bash scripts/configurar_despliegue.sh
sudo systemctl restart egraduados
```
