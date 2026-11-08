# SPA reverse proxy — 2.0.1

Новая ветка для выделенного шлюза Ubuntu 24.04 / 26.04. fwknop + nftables
работают на хосте, nginx и Nginx UI — в одном официальном Docker-контейнере.
Сайты, upstream, сертификаты, продление, конфигурация, логи и состояние nginx
управляются через Nginx UI. Certbot и хостовый nginx не используются.

## Архитектура

| Подключение | Результат |
|---|---|
| Незнакомый IP → TCP 80/443 | nftables REDIRECT → заглушка 8081/8444 |
| IPv4 с действующим SPA → TCP 80/443 | обычные сайты nginx |
| IP из `spa_web_bypass_cidrs` → TCP 80/443 | обычные сайты без SPA |
| Любой внешний IP → 9000/9080/9180 | DROP, даже после SPA |
| SSH tunnel → 127.0.0.1:9080 | полноценный Nginx UI |
| SPA IPv4 → дополнительные защищённые порты | доступ до истечения lease для новых соединений |
| Rescue CIDR → SSH | доступ независимо от SPA |

SPA использует **фактический IPv4 источника UDP**, а не адрес из payload.
HMAC, ограничение возраста пакета, persistent replay cache и отдельные ключи
клиентов сохранены. У всех клиентов общий профиль портов. Несколько IP могут
использовать один ключ; ограничение «один IP на ключ» не реализовано.

Контейнер использует host network: исходные IP видны nginx, Docker DNAT не
обходит INPUT, UI может свободно создавать HTTP и stream-конфигурации.
Доступ к новым listener-портам требует явного разрешения в firewall.
FORWARD закрыт: сервер не является маршрутизатором и не предназначен для
других контейнеров в bridge-сетях. Исходящие соединения шлюза разрешены.

## Быстрый старт

Контроллер: Linux, Python 3.11+ (для новых ansible-core может требоваться более
новый Python; pip подберёт совместимую версию из диапазона requirements).

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-controller.txt
umask 077
python3 scripts/generate-secrets.py laptop phone > group_vars/all/vault.yml
ansible-vault encrypt group_vars/all/vault.yml
```

1. Укажите адрес и SSH-пользователя в `inventory/hosts.yml`.
2. В `group_vars/all/main.yml` задайте **свой внешний административный IP/32**
   в `spa_ssh_rescue_cidrs`. Для IPv6 используйте /128. Не оставляйте примерный IP.
3. Убедитесь, что у провайдера разрешены TCP 80/443, SSH с rescue IP и UDP
   `spa_knock_udp_port`. Сохраните доступ к консоли провайдера.
4. Для существующего Docker установите `spa_install_docker: false`.
   Требуются работающий rootful Docker Engine и `docker compose` v2.
   При `true` устанавливаются `docker.io` и `docker-compose-v2` из Ubuntu;
   с ранее установленным Docker CE пакеты не смешивать.
5. Желательно заменить `latest` проверенным тегом или digest. Образ не собирается
   проектом. Одна ссылка на образ используется и при проверке, и при запуске.

```bash
ansible-playbook playbook.yml --syntax-check --ask-vault-pass
ansible-playbook playbook.yml --ask-vault-pass --ask-become-pass
ssh -N -L 127.0.0.1:9080:127.0.0.1:9080 ubuntu@SERVER
```

Откройте http://127.0.0.1:9080, выполните мастер установки UI. Если запрошен
installation secret, прочитайте его через SSH:

```bash
sudo cat /opt/spa-proxy/nginx-ui/.install_secret
```

Создайте администратора, настройте MFA, ACME account и DNS credentials в UI.
При неисправной конфигурации nginx доступ к backend UI возможен отдельным
туннелем `-L 127.0.0.1:9000:127.0.0.1:9000` и URL http://127.0.0.1:9000.

**Первое развёртывание — на чистой VM.** Это не автоматическое обновление 0.x.
Смотрите [миграцию](docs/MIGRATION.md).

## Владение настройками

Ansible постоянно управляет firewall, fwknop, Compose и systemd. Он создаёт
`nginx.conf` и `conf.d/nginx-ui.conf` **только если файла ещё нет**.
После первого запуска всё внутри `/etc/nginx` редактируется через UI и
сохраняется при повторном Ansible. Переключение `spa_stub_mode`, redirect и
`spa_http01` в YAML влияет на начальную конфигурацию; на существующем сервере
меняйте соответствующие location через редактор UI. Это намеренно исключает
двух конкурирующих владельцев nginx-конфигурации.

UI не работает в read-only: доступны редактирование, reload, сертификаты,
терминал, плагины и возможности официального образа. Docker socket включён
по умолчанию для Docker-функций; это фактически административный доступ к
хосту. UI доверяется как root-администратору. `spa_docker_socket: false`
позволяет отказаться от Docker-функций, остальные возможности сохраняются.
Не создавайте публичный proxy_pass к UI и не переносите его listener на
публичный порт: полный конфигурационный доступ позволяет админу сознательно
нарушить изоляцию. Ограничения SSH пользователя задаются вашей SSH-политикой.

## Параметры

| Переменная | Назначение / значение по умолчанию |
|---|---|
| `spa_install_docker` | Установка Docker из репозитория Ubuntu, true |
| `spa_root` | Постоянные данные, `/opt/spa-proxy`; после установки не менять без переноса |
| `spa_nginx_ui_image` | Образ `uozi/nginx-ui:latest`; фиксируйте digest |
| `spa_docker_socket` | Доступ UI к Docker, true |
| `spa_ssh_port` | Фактический порт sshd, 22; playbook не меняет sshd |
| `spa_knock_udp_port` | UDP fwknop, 62201 |
| `spa_lease_seconds` | TTL 30–3600 секунд, 300 |
| `spa_packet_max_age` | Допустимый возраст SPA 1–600 секунд, 120 |
| `spa_ssh_rescue_cidrs` | Обязательный список аварийного доступа к SSH |
| `spa_web_bypass_cidrs` | Постоянные IPv4/IPv6 сети для сайтов, [] |
| `spa_public_extra_tcp_ports` / `spa_public_extra_udp_ports` | Публичные исключения, [] |
| `spa_protected_tcp_ports` | Порты для SPA IPv4, [22] |
| `spa_protected_udp_ports` | UDP-порты для SPA IPv4, [] |
| `spa_stub_mode` | Начальный режим page / empty (444) / redirect |
| `spa_redirect_scheme` / `spa_redirect_port` | Начальный редирект на IP клиента: http / 80 |
| `spa_http01` | Начальное узкое HTTP-01 исключение, true |
| `vault_spa_clients` | Список name/key_base64/hmac_key_base64 в Vault |

Управляющие и служебные порты зарезервированы и не могут попасть в исключения.
HTTP/3 по UDP/443 в этой версии не включён: внешний веб-трафик защищается на
TCP 80/443. Это не выключает функции UI, но задаёт сетевой контракт шлюза.

## Документация и проверки

- [Сайты, сертификаты, заглушка](docs/UI-WORKFLOW.md)
- [SPA, аварийный доступ, логи, backup](docs/OPERATIONS.md)
- [Миграция с 0.x](docs/MIGRATION.md)
- [Архитектурные решения](docs/ADR.md)
- [Проверки и ограничения верификации](docs/VALIDATION.md)

```bash
python3 -m unittest discover -s tests -v
```

Официальные источники: [Docker](https://nginxui.com/guide/getting-started),
[env](https://nginxui.com/guide/env),
[сертификаты](https://nginxui.com/guide/config-cert),
[server](https://nginxui.com/guide/config-server).

## Исправление WebSocket в 2.0.1

Начальный nginx-ui.conf содержит maps для X-Forwarded-Proto/Host, требуемые
проверкой Nginx UI. Они используются только в loopback listener 9080.
Для обычного HTTP SSH-туннеля без этих заголовков сохраняются $scheme и $http_host.
Публичные upstream-конфигурации продолжают перезаписывать forwarding headers.

На уже установленном сервере шаблон не перезаписывается. Если Self Check уже
исправил файл, дополнительных изменений не требуется. Иначе используйте
System → Self Check → Attempt to fix для WebSocket reverse-proxy fix.
Сохраните копию конфигурации и проверьте nginx -t, терминал и live tail в UI.

Источник: https://nginxui.com/guide/docker-websocket-fix

## Клиенты для авторизации

- для linux / macos / android: https://github.com/Godhart/fwknop-keepalive
