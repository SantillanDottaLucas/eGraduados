server {
    listen 80;
    server_name @DOMINIOS@;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name @DOMINIOS@;

    ssl_certificate     /etc/ssl/certs/egraduados.crt;
    ssl_certificate_key /etc/ssl/private/egraduados.key;

    client_max_body_size 10m;   # igual a DJANGO_MAX_UPLOAD_SIZE

    location /static/ {
        alias @APP_DIR@/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
