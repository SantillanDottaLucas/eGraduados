[Unit]
Description=eGraduados (gunicorn)
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=@APP_DIR@
EnvironmentFile=@APP_DIR@/.env
ExecStart=@APP_DIR@/venv/bin/gunicorn egraduados_core.wsgi:application \
    --bind 127.0.0.1:8000 --workers 3 \
    --access-logfile /var/log/egraduados/access.log \
    --error-logfile /var/log/egraduados/error.log
Restart=always

[Install]
WantedBy=multi-user.target
