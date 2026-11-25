#!/usr/bin/env bash
# Genera el servicio systemd y el virtualhost de Nginx usando como
# única fuente EGRADUADOS_DIR y DJANGO_ALLOWED_HOSTS del .env.
#
# Uso:
#   bash scripts/configurar_despliegue.sh            # escribe y valida
#   bash scripts/configurar_despliegue.sh --dry-run  # sólo muestra el resultado
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVO_ENV="$PROJECT_DIR/.env"
SECADO=0

if [[ "${1:-}" == "--dry-run" ]]; then
    SECADO=1
fi

if [[ ! -f "$ARCHIVO_ENV" ]]; then
    echo "ERROR: no existe $ARCHIVO_ENV. Copiar .env.example y completarlo." >&2
    exit 1
fi

# Lee una clave CLAVE=valor del .env sin depender de python-dotenv.
leer_env() {
    local clave="$1"
    local valor
    valor="$(sed -n "s/^${clave}[[:space:]]*=[[:space:]]*//p" "$ARCHIVO_ENV" | sed -n 's/[[:space:]]*$//; 1p')"
    case "$valor" in
        \"*\") valor="${valor:1:${#valor}-2}" ;;
        \'*\') valor="${valor:1:${#valor}-2}" ;;
    esac
    printf '%s' "$valor"
}

APP_DIR="$(leer_env EGRADUADOS_DIR)"

if [[ -z "$APP_DIR" || "$APP_DIR" != /* ]]; then
    echo "ERROR: EGRADUADOS_DIR debe ser una ruta absoluta en $ARCHIVO_ENV." >&2
    exit 1
fi

if [[ "$APP_DIR" != "$PROJECT_DIR" ]]; then
    echo "ERROR: EGRADUADOS_DIR=$APP_DIR no coincide con la carpeta actual $PROJECT_DIR." >&2
    echo "Mover la carpeta, actualizar .env y volver a ejecutar el script." >&2
    exit 1
fi

HOSTS="$(leer_env DJANGO_ALLOWED_HOSTS)"
DOMINIOS="$(printf '%s' "$HOSTS" | tr ',' ' ' | tr -s '[:space:]' ' ' | sed -e 's/^ //' -e 's/ $//')"

if [[ -z "$DOMINIOS" || "$DOMINIOS" == *"*"* ]]; then
    echo "ERROR: DJANGO_ALLOWED_HOSTS debe contener dominios reales (sin comodines)." >&2
    exit 1
fi

for plantilla in \
    "$PROJECT_DIR/deploy/egraduados.service.tpl" \
    "$PROJECT_DIR/deploy/nginx-egraduados.conf.tpl"
do
    if [[ ! -f "$plantilla" ]]; then
        echo "ERROR: falta la plantilla $plantilla." >&2
        exit 1
    fi
done

generar() {
    local plantilla="$1"
    local destino="$2"
    local contenido
    contenido="$(sed -e "s|@APP_DIR@|$APP_DIR|g" -e "s|@DOMINIOS@|$DOMINIOS|g" "$plantilla")"

    if [[ $SECADO -eq 1 ]]; then
        echo "===== $destino ====="
        printf '%s\n' "$contenido"
    else
        printf '%s\n' "$contenido" | sudo tee "$destino" > /dev/null
        echo "Escrito: $destino"
    fi
}

generar "$PROJECT_DIR/deploy/egraduados.service.tpl" \
    /etc/systemd/system/egraduados.service
generar "$PROJECT_DIR/deploy/nginx-egraduados.conf.tpl" \
    /etc/nginx/sites-available/egraduados

if [[ $SECADO -eq 1 ]]; then
    echo "Modo --dry-run: no se escribió ni reinició nada."
    exit 0
fi

sudo mkdir -p /var/log/egraduados
sudo chown www-data:www-data /var/log/egraduados
sudo ln -sfn /etc/nginx/sites-available/egraduados \
    /etc/nginx/sites-enabled/egraduados
sudo systemctl daemon-reload
sudo nginx -t

echo "Listo. Aplicar con: sudo systemctl restart egraduados && sudo systemctl reload nginx"
