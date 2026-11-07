# Работа через Nginx UI

## Reverse proxy

В Sites создайте сайт, задайте домен и listen 80, затем SSL/listen 443.
Домен должен указывать на шлюз, upstream — на другой сервер.
Начальный default_server остаётся отдельным; у новых сайтов не ставьте
default_server. Пример блока location для LAN backend:

```nginx
location / {
    proxy_pass http://192.168.10.20:8080;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_read_timeout 300s;
}
```

`$connection_upgrade` уже определён в bootstrap map. X-Forwarded-For намеренно
перезаписывается на входном шлюзе, чтобы клиент не подделал цепочку адресов.
Backend должен доверять этим заголовкам только от шлюза.
Без завершающего `/` proxy_pass сохраняет исходный URI; для удаления `/app/`
используйте `location /app/ { proxy_pass http://192.168.10.20:8080/; }`.

Для upstream в интернете:

```nginx
location / {
    proxy_pass https://origin.example.net;
    proxy_ssl_server_name on;
    proxy_ssl_name origin.example.net;
    proxy_ssl_verify on;
    proxy_ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt;
    proxy_set_header Host origin.example.net;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Не указывайте домен, который резолвится обратно в шлюз: получится цикл.
LAN должен быть маршрутизируемым с VPS. `127.0.0.1` в host network — сам шлюз,
не удалённый сервер. Для private CA разместите CA в постоянном каталоге nginx
и укажите путь внутри контейнера. Не отключайте проверку TLS.
Статически заданный DNS upstream обычно обновляется при reload nginx;
для динамического DNS нужна подходящая resolver/upstream-конфигурация.

На origin ограничьте входящие подключения IP шлюза. SPA защищает вход на шлюз,
но не закрывает прямой доступ к публичному origin автоматически.
Перед включением сайта используйте nginx test и reload в UI.

## Сертификаты: только Nginx UI

В Certificates создайте ACME account, выберите CA и email. Вначале удобно
использовать staging CA. DNS-01: добавьте credentials DNS-провайдера и выпустите
сертификат для нужных имён, включая wildcard при необходимости. Плагины
официального UI не отключены. Продление выполняет Nginx UI, внешних таймеров нет.

HTTP-01: DNS A (и AAAA, если опубликован) должен вести к шлюзу. Публичный TCP/80
обязателен. Заглушка пропускает **только** `/.well-known/acme-challenge/` к
локальному challenge-серверу UI на 9180; остальные URL не уходят на сайты.
Если challenge не активен, возможен 502 — приложение при этом не раскрывается.
После создания новых HTTP-сайтов проверьте, что UI добавил ACME location;
при ручном редактировании сохраните его:

```nginx
location ^~ /.well-known/acme-challenge/ {
    proxy_pass http://127.0.0.1:9180;
    proxy_set_header Host $host;
}
```

На HTTP listener перенаправляйте HTTPS внутри `location /`, а не server-level
`return`, иначе return перехватит challenge. Не публикуйте 9180.
DNS-01 не требует HTTP-исключения: при желании удалите ACME location из
bootstrap и сайтов через UI после перехода всех сертификатов на DNS-01.

## Заглушка и редирект

Откройте `/etc/nginx/conf.d/nginx-ui.conf` в редакторе UI. Listener 8081/8444
обслуживает незарегистрированные IP для всех доменов. Изменяйте его location /:

```nginx
# Страница
default_type text/html;
return 200 '<html><body>Service unavailable</body></html>';
# Либо пустое закрытие
# return 444;
# Либо редирект на реальный IP клиента без копирования URI и query string
# return 302 http://$spa_redirect_host:80/;
```

Используйте один вариант. Map обрамляет IPv6 квадратными скобками. За NAT
получатель редиректа — публичный IP NAT, не частный адрес компьютера.
Заголовки X-Forwarded-For не определяют адрес назначения редиректа.

HTTPS сначала требует TLS handshake. Bootstrap self-signed сертификат вызывает
предупреждение браузера **до** страницы/редиректа. В UI выпустите доверенный
сертификат (обычно DNS-01) и назначьте его listener 8444. Для разных несвязанных
доменов нужны подходящие SAN или отдельные SNI server-блоки на 8444, в каждом —
только заглушка. Произвольный hostname/IP покрыть одним доверенным сертификатом
невозможно. HSTS может дополнительно препятствовать HTTP-редиректу.

Для stream TCP/UDP создавайте конфиги в UI и добавляйте их порты в
`spa_protected_*_ports` либо public exceptions, затем запускайте Ansible.
Не используйте зарезервированные порты. Не проксируйте через сайты UI-порты,
Docker API, cloud metadata и другие локальные административные интерфейсы.
