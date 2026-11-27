# eGraduados — Instalación manual paso a paso (intranet)

Este documento se basta solo. No hace falta leer ningún otro archivo para
instalar el proyecto. Está escrito para una persona que nunca instaló una
aplicación web: cada paso dice qué hacer, por qué se hace y cómo saber que salió
bien.

El enfoque es **manual**: se explica qué archivos crear y qué comandos ejecutar.
No se da por sentado que haya Nginx, ni Gunicorn, ni HTTPS. El servicio se
piensa para una **intranet** (la usan personas dentro de una organización), así
que tampoco se asume un dominio público.

Cuando un paso diga "ejecutá este comando", copiá el texto del recuadro y pegálo
en la terminal. No copiá los símbolos `$`, `>` ni los comentarios que empiezan
con `#`.

---

## Índice

1. Qué vamos a instalar
2. Palabras que conviene conocer
3. Software y versiones necesarias
4. Preparación común a todos los sistemas
5. Instalación en Windows (desarrollo local)
6. Instalación en Xubuntu / Ubuntu de escritorio
7. Instalación en Ubuntu Server para intranet
8. Otros Linux: Debian, Fedora y RHEL
9. Si algo no arranca
10. Verificación mínima
11. Operación posterior: actualizar, respaldar y mudar la carpeta
Apéndice A: qué significa cada variable del `.env`
Apéndice B: notas sobre el código del proyecto

---

## 1. Qué vamos a instalar

eGraduados es una aplicación web: un programa que se ejecuta en una computadora
y se usa desde un navegador (Chrome, Firefox, Edge). Está escrita en Python con
el framework Django y guarda los datos en una base de datos.

- **Windows:** desarrollo y pruebas en la propia computadora. Se usa MySQL
  (también en desarrollo) y el servidor que trae Django (`runserver`).
- **Xubuntu / Ubuntu de escritorio:** igual que Windows, pero en Linux. Sirve
  para desarrollar y para probar la aplicación en la red interna.
- **Ubuntu Server en intranet:** la aplicación queda prendida en un servidor al
  que acceden las personas de la organización. MySQL es la única base
  soportada. Cómo se mantenga prendida y si se pone delante un Nginx son
  decisiones que se explican como opciones, no como obligaciones.

Necesitás la carpeta del proyecto ya descargada, conexión a Internet para
descargar las librerías y permisos de administrador en Linux. No necesitás saber
Django ni administrar servidores para seguir los pasos.

---

## 2. Palabras que conviene conocer

- **Terminal / consola:** ventana donde escribís comandos. En Windows se llama
  PowerShell; en Linux, Terminal.
- **Comando:** una instrucción escrita en la terminal. Por ejemplo
  `python --version` pregunta qué versión de Python hay.
- **Ruta (path):** dirección de una carpeta o archivo. Una ruta absoluta empieza
  desde la raíz: `C:/Users/...` en Windows, `/home/usuario/...` en Linux.
- **Entorno virtual (`venv`):** carpeta dentro del proyecto donde se instalan
  las librerías sólo para este proyecto. Evita mezclarlas con otros programas.
- **`pip`:** instalador de librerías de Python. Lee `requirements.txt`.
- **`.env`:** archivo de configuración con rutas y claves. Es secreto: nunca se
  sube a Internet ni se comparte. Es la **única fuente** de configuración:
  Django lo lee siempre y sobreescribe cualquier variable del entorno.
- **`manage.py`:** archivo del proyecto que recibe los comandos de
  administración. Siempre se ejecuta desde la carpeta del proyecto.
- **Base de datos:** donde se guardan graduados, exámenes y usuarios. Se usa
  MySQL en todos los entornos; el proyecto no soporta SQLite.
- **Servidor web:** programa que entrega la página al navegador. Nginx es una
  opción, no la única.
- **Servidor WSGI:** programa que ejecuta Django de forma estable. Gunicorn es
  una opción; también existen uWSGI y Waitress.
- **systemd:** parte de Linux que mantiene servicios corriendo y los inicia al
  encender. Es una comodidad, no un requisito para probar.
- **HTTPS / TLS:** conexión segura con certificado. En una intranet cerrada no
  es obligatorio; se explica cómo activarlo más adelante.
- **`sudo`:** "hacé esto como administrador" en Linux. Pide tu contraseña.
- **`Ctrl+C`:** teclas para detener un programa que está corriendo en la
  terminal, por ejemplo `runserver`.

---

## 3. Software y versiones necesarias

Usá estas versiones. Otras pueden traer errores difíciles de diagnosticar.

- **Sistema operativo para desarrollo:** Windows 10 u 11, o Xubuntu/Ubuntu
  24.04 LTS o 26.04 LTS. Los LTS (Xubuntu, Kubuntu, etc.) reciben
  actualizaciones por 3 años.
- **Sistema operativo para el servidor de intranet:** Ubuntu Server 24.04 LTS o
  26.04 LTS (5 años de soporte). También sirve Debian 13 o Fedora/RHEL con los
  ajustes de la sección 8.
- **Python:** 3.13 (probado con 3.13.15). Django 6.1.1 necesita 3.12 o superior,
  pero las librerías fijadas se probaron con 3.13. No usar 3.14/3.15 sin probar.
- **Django:** 6.1.1, fijado en `requirements.txt`.
- **Base de datos:** MySQL 8.0/8.4 o MariaDB 10.11+ en desarrollo y en
  intranet. El servicio debe estar corriendo antes de ejecutar cualquier
  comando de Django. SQLite quedó fuera de soporte.
- **Cliente MySQL de Python:** `mysqlclient` 2.3.0. En Windows ya viene
  compilado; en Ubuntu necesita paquetes de desarrollo (`default-libmysqlclient-dev`).
- **Servidor WSGI (sugerencia):** Gunicorn 27.0.1, que se instala automáticamente
  sólo en Linux. Podés usar uWSGI o Waitress en su lugar, o `runserver` para
  pruebas internas.
- **Proxy inverso (sugerencia):** Nginx. No es obligatorio en una intranet;
  sirve para archivos estáticos, proxy inverso y, si se quiere, HTTPS.

Dependencias que instala `pip` desde `requirements.txt`, con sus versiones
exactas:

- asgiref 3.12.1 (transitiva de Django).
- Django 6.1.1 (directa; framework web).
- docxtpl 0.20.2 (directa; genera los `.docx`).
- et_xmlfile 2.0.0 (transitiva de openpyxl).
- Jinja2 3.1.6 (transitiva de docxtpl).
- lxml 6.1.3 (transitiva de docxtpl).
- MarkupSafe 3.0.4 (transitiva de Jinja2).
- mysqlclient 2.3.0 (directa; conexión a MySQL).
- numpy 2.5.3 (transitiva de pandas).
- openpyxl 3.1.5 (directa; lectura de `.xlsx`).
- pandas 3.0.5 (directa; lectura de planillas).
- python-dateutil 2.9.0.post0 (transitiva de pandas).
- python-docx 1.2.0 (directa; uso directo en plantillas y tests).
- python-dotenv 1.2.4 (directa; lectura del `.env`).
- six 1.17.0 (transitiva de python-dateutil).
- sqlparse 0.6.0 (transitiva de Django).
- tzdata 2026.4 (transitiva de Django/pandas).
- xlrd 2.0.2 (directa; lectura de `.xls` antiguos).
- gunicorn 27.0.1 (sugerencia; sólo se instala en Linux).

No hacen falta `flake8`, `pylint`, `isort` ni `django-debug-toolbar` para
ejecutar el sistema.

**Python en Ubuntu:** Ubuntu 24.04 trae Python 3.12 y Ubuntu 26.04 trae 3.14
como intérprete del sistema, y ninguno ofrece `python3.13` en sus repositorios
oficiales. Se instala desde el repositorio externo `deadsnakes`, sin reemplazar
`/usr/bin/python3` (las herramientas del sistema dependen de él). Debian 13 ya
trae Python 3.13 y no necesita ese paso.

---

## 4. Preparación común a todos los sistemas

- **Descargar el proyecto.** Si usás Git en Linux:

  ```bash
  mkdir -p ~/proyectos
  cd ~/proyectos
  git clone <url-del-repositorio> egraduados
  ```

  En Windows podés clonar con Git o descargar el ZIP y descomprimirlo. Anotá la
  ruta completa: la vas a necesitar en el `.env`. El nombre de la carpeta es
  libre; puede ser `egraduados`, `B-Codigo` o cualquier otro.

- **El `.env` va al lado de `manage.py` y es obligatorio.** Si falta, Django no
  arranca. El proyecto busca su configuración dentro de su propia carpeta
  (`BASE_DIR / ".env"`) y la carga con `override=True`: las variables que
  hubiera en la terminal, en systemd o en Docker **no** pueden reemplazar lo
  que diga el archivo. Copiá la plantilla:

  - Linux: `cp .env.example .env`
  - Windows: `Copy-Item .env.example .env`

  El `.env` que creaste no se sube a Git: contiene claves privadas.

- **`EGRADUADOS_DIR` es la ruta de la carpeta.** Ese valor lo usa el script
  opcional de despliegue para generar archivos de servicio. Django no lo lee
  cuando la aplicación está corriendo, porque para encontrar el `.env` ya hay
  que saber dónde está la carpeta.

- **Regla de oro del `.env`:** cada clave aparece **una sola vez**. Si dejás dos
  líneas `DJANGO_DB_NAME`, la última gana y la primera se ignora en silencio.
  Cuando pongas un bloque de configuración nuevo, **reemplazá** el anterior;
  nunca lo agregues debajo.

- **Cargar los datos con el `.sql`.** Los datos se cargan ejecutando un archivo
  SQL que va en `scripts/`; el nombre exacto lo define quien lo cree, por ejemplo
  `scripts/<nombre-del-script>.sql`. Ese paso se explica en cada sistema. No hay
  ningún comando `manage.py` que haga esa carga: se ejecuta el `.sql` con tu
  cliente de base de datos y listo.

- **Usuario inicial.** Después de migrar se crea con:

  ```bash
  python manage.py crear_usuario_admin --email admin@gmail.com --nombre "Administrador"
  ```

  El email debe terminar en `@gmail.com` (regla del sistema) y el código de
  acceso de 6 caracteres se imprime **una sola vez**. Copialo antes de cerrar la
  terminal: no se envía por correo y no se puede volver a ver.

---

## 5. Instalación en Windows (desarrollo local)

### Paso 5.1 — Instalar Python 3.13

Con `winget`:

```powershell
winget install Python.Python.3.13
```

O descargá el instalador de `https://www.python.org/downloads/`, ejecutalo y
marcá la casilla "Add Python to PATH". Verificá:

```powershell
py -3.13 --version
```

Debe mostrar `Python 3.13.x`. Usá siempre `py -3.13`: el comando suelto
`python` en Windows suele abrir la Microsoft Store.

### Paso 5.2 — Crear el entorno virtual e instalar librerías

```powershell
cd C:\Users\Usuario\Documents\eGraduados\B-Codigo
py -3.13 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Si aparece un mensaje en rojo que dice que la ejecución de scripts está
deshabilitada, ejecutá esto y repetí la activación:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Cuando el entorno está activado, el prompt muestra `(venv)` al principio. Si no
querés activarlo, podés llamar directo a `.\venv\Scripts\python.exe`.

### Paso 5.3 — Escribir el `.env` correcto

```powershell
Copy-Item .env.example .env
notepad .env
```

Borrá todo el contenido y dejá **este único bloque** (cambiá la ruta y los datos
de MySQL por los tuyos):

```ini
EGRADUADOS_DIR=C:/Users/Usuario/Documents/eGraduados/B-Codigo
DJANGO_DEBUG=1
DJANGO_SECRET_KEY=<secret-generado-abajo>
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_HABILITAR_ADMIN=1
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

DJANGO_DB_NAME=egraduados
DJANGO_DB_USER=root
DJANGO_DB_PASSWORD=
DJANGO_DB_HOST=127.0.0.1
DJANGO_DB_PORT=3306
```

Generá el secreto en la misma terminal:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Usá `/` en las rutas de Windows. El motor de base de datos **no se configura**:
está fijo en MySQL dentro de `settings.py`. No escribas `DJANGO_DB_ENGINE` ni
`DJANGO_READ_DOTENV`: se ignoran. Todas las claves del bloque son obligatorias;
si falta el `.env` o alguna clave, Django no arranca. El `.env` gana siempre
sobre las variables de la terminal: si tenés una variable con el mismo nombre,
cerrá la terminal y abrila de nuevo.

### Paso 5.4 — Crear la base y las tablas

Instalá MySQL Server 8.x desde el sitio oficial y creá la base con:

```sql
CREATE DATABASE egraduados CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Después, en la carpeta del proyecto:

```powershell
python manage.py migrate
```

Se puede ejecutar las veces que haga falta: no borra datos.

### Paso 5.5 — Cargar los datos desde el `.sql`

Cuando el archivo de datos exista en `scripts/` (por ejemplo
`scripts/<nombre-del-script>.sql`), hacé esto a mano:

- Abrí MySQL Workbench y conectate con el usuario del `.env`.
- *File → Open SQL Script*, elegí el archivo y presioná *Execute*.
- Si el `.sql` empieza con `use egraduados;`, funciona bien en MySQL.

Si el `.sql` todavía no existe, saltate este paso y volvé cuando lo creen. No
hay ningún comando especial de Django para hacerlo.

### Paso 5.6 — Crear el usuario administrador

```powershell
python manage.py crear_usuario_admin --email admin@gmail.com --nombre "Administrador"
```

Copiá el código de 6 caracteres que muestra.

### Paso 5.7 — Arrancar y probar

```powershell
python manage.py runserver
```

Abrí `http://127.0.0.1:8000` e ingresá con el email y el código. `Ctrl+C` en la
terminal detiene el servidor.

> MySQL es obligatorio también en Windows: no hay modo SQLite. No hace falta
> instalar un conector extra: `mysqlclient` ya trae la parte compilada para
> Windows con Python 3.13.

---

## 6. Instalación en Xubuntu / Ubuntu de escritorio

Sirve para Xubuntu, Ubuntu, Kubuntu, Linux Mint, etc. Es para desarrollo y
pruebas en la red interna. Para dejar el servicio en un servidor, usá la
sección 7.

### Paso 6.1 — Herramientas base

```bash
sudo apt update
sudo apt install -y software-properties-common git curl build-essential pkg-config \
    default-libmysqlclient-dev
```

`sudo` pide tu contraseña. Mientras la escribís no se ve nada en pantalla: es
normal.

### Paso 6.2 — Python 3.13

```bash
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev
python3.13 --version
```

No cambies el `python3` por defecto del sistema: Xubuntu 24.04 usa 3.12 y
26.04 usa 3.14 internamente. Nosotros llamamos a `python3.13` de forma
explícita. En Debian 13 saltate el PPA: `python3` ya es 3.13.

### Paso 6.3 — Proyecto y entorno virtual

```bash
mkdir -p ~/proyectos
cd ~/proyectos
git clone <url-del-repositorio> egraduados
cd egraduados
python3.13 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Paso 6.4 — `.env`

```bash
cp .env.example .env
nano .env
```

Reemplazá todo por un único bloque (poné tu ruta, tu secreto y tus datos de
MySQL):

```ini
EGRADUADOS_DIR=/home/<usuario>/proyectos/egraduados
DJANGO_DEBUG=1
DJANGO_SECRET_KEY=<secret-generado-con-get_random_secret_key>
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_HABILITAR_ADMIN=1
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

DJANGO_DB_NAME=egraduados
DJANGO_DB_USER=egraduados
DJANGO_DB_PASSWORD=clave-segura
DJANGO_DB_HOST=127.0.0.1
DJANGO_DB_PORT=3306
```

En `nano`: escribí con las flechas, guardá con `Ctrl+O` y `Enter`, salí con
`Ctrl+X`. El motor está fijo en MySQL: no escribas `DJANGO_DB_ENGINE` ni
`DJANGO_READ_DOTENV`. El `.env` manda sobre cualquier variable de la terminal.

### Paso 6.5 — MySQL, inicializar, cargar datos y probar

```bash
sudo apt install -y mysql-server
sudo mysql
```

Dentro de MySQL:

```sql
CREATE DATABASE egraduados CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'egraduados'@'localhost' IDENTIFIED BY 'clave-segura';
GRANT ALL PRIVILEGES ON egraduados.* TO 'egraduados'@'localhost';
FLUSH PRIVILEGES;
exit
```

Después, en la carpeta del proyecto:

```bash
python manage.py migrate
python manage.py crear_usuario_admin --email admin@gmail.com --nombre "Administrador"
python manage.py test
python manage.py runserver
```

La carga del `.sql` se hace a mano con MySQL Workbench o el cliente de MySQL,
igual que en el paso 5.5. `manage.py test` tarda un par de minutos y debe
terminar con `OK`. Para detener el servidor, `Ctrl+C`.

Con `DJANGO_DEBUG=1`, `runserver` sirve los estilos automáticamente y alcanza
para probar desde otros equipos de la intranet si levantás el servidor con
`python manage.py runserver 0.0.0.0:8000` y abrís `http://<ip-de-tu-equipo>:8000`.

---

## 7. Instalación en Ubuntu Server para intranet

Acá la aplicación queda accesible para las personas de la organización. No se
asume salida a Internet, dominio público ni certificado: todo se ajusta a un
nombre o IP interna.

### Paso 7.1 — Preparar el servidor

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev default-libmysqlclient-dev \
    build-essential pkg-config git software-properties-common mysql-client
```

Agregá `mysql-server` a la lista si la base va en el mismo servidor. Si la base
está en otro equipo, alcanza con `mysql-client`.

```bash
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev
python3.13 --version
```

### Paso 7.2 — Instalar el proyecto

Elegí la carpeta; acá se usa `/srv/egraduados/egraduados` de ejemplo:

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

### Paso 7.3 — Base de datos (si es local)

```bash
sudo mysql
```

```sql
CREATE DATABASE egraduados CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'egraduados'@'localhost' IDENTIFIED BY 'clave-segura';
GRANT ALL PRIVILEGES ON egraduados.* TO 'egraduados'@'localhost';
FLUSH PRIVILEGES;
exit
```

`utf8mb4` permite guardar tildes, ñ y otros caracteres.

### Paso 7.4 — `.env` para intranet sin HTTPS

Generá primero una clave secreta nueva:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Después escribí el `.env` con `nano .env` y dejá **un solo bloque**:

```ini
EGRADUADOS_DIR=/srv/egraduados/egraduados
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<pegar-la-clave-generada-arriba>
DJANGO_ALLOWED_HOSTS=egraduados.interna,10.0.0.5
DJANGO_CSRF_TRUSTED_ORIGINS=http://egraduados.interna
DJANGO_HABILITAR_ADMIN=0
DJANGO_DB_NAME=egraduados
DJANGO_DB_USER=egraduados
DJANGO_DB_PASSWORD=clave-segura
DJANGO_DB_HOST=127.0.0.1
DJANGO_DB_PORT=3306
DJANGO_SECURE_SSL_REDIRECT=0
DJANGO_SECURE_HSTS_SECONDS=0
DJANGO_EMAIL_HOST=smtp.interna
DJANGO_EMAIL_PORT=25
DJANGO_DEFAULT_FROM_EMAIL=egraduados@unpa.edu.ar
```

Puntos clave:

- `DJANGO_ALLOWED_HOSTS` lleva el nombre interno y/o la IP sin `http://` y sin
  comodines (`*`). Si entrás por IP, tiene que estar la IP; si entrás por
  nombre, el nombre.
- `DJANGO_CSRF_TRUSTED_ORIGINS` **sí** lleva esquema: `http://...` porque no hay
  TLS. Si más adelante agregás HTTPS, cambialo a `https://...`.
- Con `DJANGO_DEBUG=0`, el código fuerza HTTPS por defecto. Por eso se ponen
  `DJANGO_SECURE_SSL_REDIRECT=0` y `DJANGO_SECURE_HSTS_SECONDS=0`. Si no los
  ponés, la intranet va a redirigir a HTTPS y no va a abrir.
- `DJANGO_SECRET_KEY` es obligatorio siempre (también con `DEBUG=1`). La clave
  debe ser aleatoria y de 50 o más caracteres.
- El `.env` se carga con `override=True`: lo que diga el archivo gana sobre
  `EnvironmentFile` de systemd, Docker o cualquier export de la terminal.
  Si una clave no está en el archivo, Django no arranca.
- No escribas `DJANGO_DB_ENGINE` ni `DJANGO_READ_DOTENV`: quedaron fuera de
  soporte. El motor es MySQL fijo.
- Nada de `export`, nada de espacios alrededor de `=`, nada de comentarios al
  final de una línea. Si un valor tiene espacios o `#`, citarlo con comillas
  dobles.

Permisos para que el servicio pueda leer el archivo:

```bash
sudo chown "$USER:www-data" .env
sudo chmod 640 .env
```

### Paso 7.5 — Tablas, datos y usuario

```bash
cd /srv/egraduados/egraduados
source venv/bin/activate
python manage.py check
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py crear_usuario_admin --email admin@gmail.com --nombre "Administrador"
```

`collectstatic` junta los estilos y scripts en `staticfiles/`. Hacelo aunque no
uses Nginx: los necesitás si más adelante ponés un servidor web o WhiteNoise.

La carga del `.sql` es manual: abrí el archivo `scripts/<nombre-del-script>.sql`
con tu cliente MySQL (Workbench u otro) y ejecutalo. Si el archivo incluye
`use egraduados;`, funciona bien en MySQL.

No hay ningún paso de "recalcular" ni comando especial de carga: los datos
entran con el `.sql` y ya están.

### Paso 7.6 — Cómo mantener la aplicación corriendo (opciones)

Elegí la opción que se ajuste a tu servidor. Ninguna es obligatoria para probar.

- **Para pruebas internas:** `python manage.py runserver 0.0.0.0:8000` con
  `DJANGO_DEBUG=1`. Es lo más simple, pero no conviene dejarlo así de forma
  permanente: no está pensado para múltiples usuarios ni para servir archivos
  estáticos con `DEBUG=0`.
- **Sugerencia habitual:** Gunicorn, que ya quedó instalado por
  `requirements.txt`. Arranca así:

  ```bash
  gunicorn egraduados_core.wsgi:application --bind 0.0.0.0:8000 --workers 3
  ```

  Escucha en todas las interfaces de la intranet. Si vas a poner Nginx delante,
  cambialo a `--bind 127.0.0.1:8000` para que Gunicorn no quede expuesto
  directamente.
- **Otras opciones válidas:** uWSGI o Waitress, con los mismos argumentos
  básicos (módulo `egraduados_core.wsgi:application`, puerto 8000). Elegí la que
  tu equipo ya use en otros servicios.

Si con `DEBUG=0` no ves los estilos, es porque Django no sirve `staticfiles/`
por sí mismo. Necesitás que los sirva Nginx, o agregar WhiteNoise al proyecto.
No es un error de instalación: es una decisión de diseño de Django.

### Paso 7.7 — Nginx (opcional)

Poner Nginx delante no es obligatorio en una intranet. Conviene si querés:

- servir `/static/` sin agregar otra dependencia;
- tener un único punto de entrada en el puerto 80;
- agregar HTTPS más adelante;
- ocultar el puerto 8000 del servidor WSGI.

Si decidís usarlo:

```bash
sudo apt install -y nginx
sudo nano /etc/nginx/sites-available/egraduados
```

Pegá este ejemplo (cambiá la ruta y el nombre/IP por los tuyos):

```nginx
server {
    listen 80;
    server_name egraduados.interna 10.0.0.5;

    client_max_body_size 10m;

    location /static/ {
        alias /srv/egraduados/egraduados/staticfiles/;
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

`client_max_body_size 10m` coincide con `DJANGO_MAX_UPLOAD_SIZE=10485760`.
Después:

```bash
sudo ln -s /etc/nginx/sites-available/egraduados /etc/nginx/sites-enabled/egraduados
sudo nginx -t
sudo systemctl reload nginx
```

Si no usás Nginx, no ejecutes nada de este paso.

### Paso 7.8 — systemd (opcional)

Para que el servicio arranque solo al encender y se reinicie si se cae, podés
crear un archivo de servicio. Este ejemplo asume que elegiste Gunicorn:

```bash
sudo nano /etc/systemd/system/egraduados.service
```

```ini
[Unit]
Description=eGraduados en intranet
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/srv/egraduados/egraduados
EnvironmentFile=/srv/egraduados/egraduados/.env
ExecStart=/srv/egraduados/egraduados/venv/bin/gunicorn egraduados_core.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

Si tu servidor WSGI es otro, cambiá sólo la línea `ExecStart` por el comando
equivalente. Las rutas van escritas literalmente: systemd no acepta variables
en `WorkingDirectory=` ni en la ruta de `EnvironmentFile=`.

Para activarlo:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now egraduados
sudo systemctl status egraduados
```

Si elegiste u otra forma de arranque, podés omitir este paso.

### Paso 7.9 — Atajo opcional (sólo si usás Nginx)

El repositorio trae `scripts/configurar_despliegue.sh` y plantillas en
`deploy/`. El script lee `EGRADUADOS_DIR` y `DJANGO_ALLOWED_HOSTS` del `.env`,
valida que la ruta coincida con la carpeta actual y genera el servicio systemd y
el virtualhost de Nginx con las rutas ya rellenas:

```bash
bash scripts/configurar_despliegue.sh --dry-run
bash scripts/configurar_despliegue.sh
```

El `--dry-run` sólo muestra los archivos, no escribe nada. Es un atajo para no
copiar a mano los bloques de los pasos 7.7 y 7.8: **si decidiste no usar Nginx,
no lo ejecutes**. Si cambiás la ruta o los dominios, actualizá el `.env` y
volvé a ejecutarlo.

### Paso 7.10 — Si más adelante querés HTTPS

- Instalá el certificado que corresponda a tu organización.
- En la configuración de Nginx agregá `listen 443 ssl;` y las líneas
  `ssl_certificate` y `ssl_certificate_key` con las rutas reales.
- En el `.env` volvé a poner `DJANGO_SECURE_SSL_REDIRECT=1`,
  `DJANGO_SECURE_HSTS_SECONDS=31536000` y
  `DJANGO_CSRF_TRUSTED_ORIGINS=https://tu-nombre-interno`.
- Recargá Nginx y reiniciá el servicio.

---

## 8. Otros Linux: Debian, Fedora y RHEL

- **Debian 13:** ya trae Python 3.13, así que no se agrega deadsnakes.

  ```bash
  sudo apt update
  sudo apt install -y python3-venv python3-dev default-libmysqlclient-dev \
      build-essential pkg-config nginx mysql-client git
  python3 --version
  ```

  Desde ahí se sigue la sección 7 usando `python3 -m venv venv`. Las rutas y el
  usuario `www-data` son iguales que en Ubuntu.

- **Fedora / RHEL / Rocky / AlmaLinux:**

  ```bash
  sudo dnf install python3.13 python3.13-devel gcc mariadb-connector-c-devel nginx git
  python3.13 -m venv venv
  source venv/bin/activate
  python -m pip install -r requirements.txt
  ```

  Tres diferencias: el usuario del servicio es `nginx` en vez de `www-data`;
  Nginx no usa `sites-available`/`sites-enabled` sino `/etc/nginx/conf.d/`; y si
  usás el script opcional hay que cambiar esos dos valores en él.

- **Cualquier otra distribución:** la condición real es tener Python 3.13 y
  poder instalar `requirements.txt`. Si el sistema no ofrece 3.13, otra opción
  es instalarlo con `uv python install 3.13` y crear el venv con
  `uv venv --python 3.13`. Lo demás depende de las rutas de tu distribución.

---

## 9. Si algo no arranca

- **Error `DisallowedHost: Invalid HTTP_HOST header: '127.0.0.1:8000'`:** el
  valor que manda es el del `.env`, no el de la terminal. Revisá que
  `DJANGO_ALLOWED_HOSTS` esté una sola vez en el archivo y que incluya el host
  con el que entrás. Si habías iniciado el servidor antes de editar el `.env`,
  detenelo con `Ctrl+C` y volvé a arrancarlo: la configuración se lee al
  iniciar.

- **Error `Falta el archivo de configuración .../.env` o `La variable ... debe
  estar definida en .env`:** el `.env` no está al lado de `manage.py` o le falta
  alguna clave obligatoria. Copiá `.env.example`, completá **todas** las claves
  del bloque y guardá sin comentarios al final de las líneas.

- **Error de MySQL (`Unknown database 'egraduados'` o `Access denied ...`):** el
  `.env` es la única fuente: revisá `DJANGO_DB_NAME`, `DJANGO_DB_USER` y
  `DJANGO_DB_PASSWORD` (si la clave está vacía, dejá `DJANGO_DB_PASSWORD=`). Después
  creá la base con `utf8mb4` y otorgá permisos al usuario, como en los pasos 5.4
  y 6.5. Ya no existe la alternativa SQLite.

- **Escribo `python` y se abre Microsoft Store:** es el alias de Windows. Usá
  `py -3.13` o `.\venv\Scripts\python.exe`.

- **`No module named django`:** el entorno virtual no está activado o no se
  instalaron las librerías. Activá el venv y ejecutá
  `python -m pip install -r requirements.txt`.

- **`The script Activate.ps1 cannot be loaded`:** politics de ejecución de
  PowerShell. Ejecutá `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
  y activá de nuevo.

- **Error compilando `mysqlclient` en Ubuntu:** faltan los paquetes de
  desarrollo. Instalá `default-libmysqlclient-dev build-essential pkg-config
  python3.13-dev`. En Windows, usá Python 3.13 para aprovechar el wheel ya
  compilado.

- **`El email debe ser una cuenta de Gmail (@gmail.com)`:** es una regla del
  sistema, no un error de instalación. Usá una cuenta `@gmail.com`.

- **La página se ve sin estilos con `DEBUG=0`:** Django no sirve `staticfiles/`
  por sí mismo. Ejecutá `collectstatic` y configurá Nginx, WhiteNoise u otro
  servidor de archivos estáticos.

- **Error 502 si usás Nginx + Gunicorn:** revisá
  `sudo systemctl status egraduados` y `/var/log/egraduados/error.log` (o el
  archivo de log que hayas elegido). Casi siempre es una ruta mal escrita en
  `WorkingDirectory=` o en `ExecStart`.

- **El script opcional dice que la ruta no coincide:** ejecutalo desde la
  carpeta del proyecto y comprobá que `EGRADUADOS_DIR` coincide con esa ruta.
  Si hay comodines en `DJANGO_ALLOWED_HOSTS`, reemplazalos por nombres reales.

---

## 10. Verificación mínima

Estas cinco comprobaciones alcanzan. No hace falta nada más.

- Versión: dentro del venv, `python -c "import django; print(django.get_version())"`
  debe mostrar `6.1.1`.
- Arranque: `python manage.py check` debe decir *"System check identified no
  issues"*. Para intranet sin HTTPS, `check --deploy` puede mostrar avisos de
  seguridad esperables: son consecuencia de haber elegido HTTP, no un fallo.
- Acceso: abrir `http://127.0.0.1:8000` en desarrollo, o la IP/nombre interno en
  el servidor, y ver la pantalla de ingreso.
- Datos: después de ejecutar el `.sql`, confirmar que las escuelas y carreras
  aparecen en la pantalla correspondiente.
- Funcionalidad: ingresar con el email y el código de 6 caracteres, cargar un
  analítico, validarlo y descargar el `.docx`. El archivo debe abrirse.

Si los estilos no cargan, volvé al punto de `staticfiles/` de la sección 9.

---

## 11. Operación posterior: actualizar, respaldar y mudar la carpeta

- **Actualizar el código (Linux):**

  ```bash
  cd /srv/egraduados/egraduados
  git pull
  source venv/bin/activate
  python -m pip install -r requirements.txt
  python manage.py migrate
  python manage.py collectstatic --noinput
  ```

  Si usás systemd: `sudo systemctl restart egraduados`. Si usás Nginx y
  cambió su configuración: `sudo systemctl reload nginx`. En Windows es igual
  pero sin `sudo` ni servicios: `git pull`, instalar dependencias, `migrate` y
  `runserver`.
  No ejecutes de nuevo la carga del `.sql` salvo que quieras recargar los datos
  desde cero: los `INSERT` pueden duplicar registros.

- **Respaldos con MySQL:**

  ```bash
  mysqldump -u egraduados -p egraduados > respaldo.sql
  ```

  Guardar el archivo fuera del servidor. Para restaurar:

  ```bash
  mysql -u egraduados -p egraduados < respaldo.sql
  ```

  También conviene guardar una copia privada del `.env`: si se pierde el
  servidor, se pierden las claves.

- **Mudar o renombrar la carpeta:** moverla, actualizar `EGRADUADOS_DIR` en el
  `.env` de la nueva ubicación y ejecutar el script opcional desde la nueva
  carpeta si se usa Nginx. Después reiniciar los servicios. Las rutas de los
  archivos creados a mano (systemd y Nginx) hay que editarlas con `nano` si
  cambiaron.

---

## Apéndice A: qué significa cada variable del `.env`

- `EGRADUADOS_DIR`: ruta absoluta de la carpeta. La usa el script opcional;
  Django no la lee enruntime.
- `DJANGO_DEBUG`: modo desarrollo. En local `1`; en el servidor `0`.
- `DJANGO_SECRET_KEY`: clave criptográfica. **Obligatoria siempre**, aleatoria y
  de 50+ caracteres. No hay valor de desarrollo incorporado en el código.
- `DJANGO_ALLOWED_HOSTS`: nombres o IPs permitidos, separados por comas. Sin
  `http://` y sin comodines.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: orígenes permitidos para formularios. Lleva
  esquema: `http://...` en intranet sin TLS, `https://...` con TLS.
- `DJANGO_HABILITAR_ADMIN`: habilita `/admin/`. En desarrollo `1`, en el
  servidor conviene `0`.
- `DJANGO_DB_NAME`: nombre de la base MySQL. **Sólo una vez en el archivo.**
- `DJANGO_DB_USER` / `DJANGO_DB_PASSWORD`: usuario y clave de MySQL. La clave
  puede estar vacía (`DJANGO_DB_PASSWORD=`), pero la línea debe existir.
  `DJANGO_DB_ENGINE` y `DJANGO_READ_DOTENV` ya no se usan: el motor es MySQL
  fijo y el `.env` se lee siempre.
- `DJANGO_DB_HOST` / `DJANGO_DB_PORT`: dónde escucha MySQL, normalmente
  `127.0.0.1` y `3306`.
- `DJANGO_SESSION_COOKIE_AGE`: duración de la sesión en segundos (28800 = 8 h).
- `DJANGO_LOGIN_MAX_INTENTOS`: intentos fallidos antes de bloquear (5).
- `DJANGO_LOGIN_BLOQUEO_SEGUNDOS`: tiempo de bloqueo (300).
- `DJANGO_MAX_UPLOAD_SIZE`: tamaño máximo de subida en bytes (10485760 = 10 MB).
  Debe coincidir con `client_max_body_size` si se usa Nginx.
- `DJANGO_SECURE_SSL_REDIRECT`: forzar HTTPS. En intranet sin certificado, `0`;
  con HTTPS, `1`.
- `DJANGO_SECURE_HSTS_SECONDS`: tiempo de "sólo HTTPS" en el navegador. En
  intranet sin certificado, `0`.
- `DJANGO_EMAIL_BACKEND`: cómo se envían los correos. En desarrollo,
  `django.core.mail.backends.console.EmailBackend` los muestra en pantalla.
- `DJANGO_EMAIL_HOST` / `DJANGO_EMAIL_PORT` / `DJANGO_EMAIL_HOST_USER` /
  `DJANGO_EMAIL_HOST_PASSWORD` / `DJANGO_EMAIL_USE_TLS` / `DJANGO_EMAIL_USE_SSL`:
  datos del servidor SMTP. TLS y SSL son mutuamente excluyentes.
- `DJANGO_DEFAULT_FROM_EMAIL`: remitente de los correos.

El `.env` se carga con `override=True`: gana sobre las variables definidas en
el entorno del proceso (terminal, systemd, Docker). Si falta el archivo o una
clave obligatoria, Django no arranca (ver sección 9).

---

## Apéndice B: notas sobre el código del proyecto

- La ruta de la carpeta es configurable: `EGRADUADOS_DIR` alimenta el script
  opcional de despliegue. No hay una ruta `B-Codigo` fijada en el código.
- Las plantillas `.docx` se buscan con una ruta absoluta basada en `BASE_DIR`,
  así que funcionan con `runserver` o con cualquier servidor WSGI sin importar
  desde dónde se arranque el proceso.
- `requirements.txt` tiene las dependencias directas y transitivas fijadas con
  `==`. Se eliminaron `opencv-python`, `pymupdf`, `rapidocr-onnxruntime`,
  `pillow` y `colorama` porque ya no se usan. `pypdf` sí se usa para contar
  las páginas del PDF generado por LibreOffice al verificar analíticos.
- `crear_usuario_admin` crea los roles base y el usuario administrador de la
  aplicación (tabla `USUARIO`). Lee `EGRADUADOS_ADMIN_EMAIL` y
  `EGRADUADOS_ADMIN_NOMBRE` del entorno si no se pasan `--email` / `--nombre`,
  exige email `@gmail.com`, guarda el código hasheado y lo muestra una sola vez.
  `createsuperuser` de Django no reemplaza este paso.
- No existe un comando `cargar_datos_reales`. Los datos se cargan ejecutando el
  archivo `.sql` con tu cliente de base de datos, como se explica en los pasos
  5.5, 6.5 y 7.5. El nombre del archivo lo define quien lo cree; se espera que
  quede en `scripts/`.
- `scripts/configurar_despliegue.sh` y las plantillas de `deploy/` son un atajo
  opcional pensado para quien elija Nginx. No son parte de la instalación
  manual.
