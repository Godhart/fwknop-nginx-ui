# Эксплуатация

## Клиент SPA

Установите fwknop client. Создайте `~/.fwknoprc` с правами 0600:

```ini
[gateway]
SPA_SERVER SERVER_IPV4
SPA_SERVER_PORT 62201
SPA_SERVER_PROTO udp
ACCESS tcp/443
ALLOW_IP 0.0.0.0
KEY_BASE64 REPLACE_WITH_CLIENT_KEY
HMAC_KEY_BASE64 REPLACE_WITH_CLIENT_HMAC
USE_HMAC Y
```

```bash
fwknop -n gateway
ssh -N -L 127.0.0.1:9080:127.0.0.1:9080 ubuntu@SERVER_IPV4
```

ALLOW_IP не используется сервером для доверия: helper получает `$PKT_SRC`.
Не добавляйте SSH-порт в ACCESS: фиксированная заявка tcp/443 открывает общий
профиль, включая `spa_protected_tcp_ports`. Повторная SPA продлевает lease;
интервал keepalive должен быть заметно меньше TTL, например 60 при TTL 300.
При смене внешнего IP отправьте SPA заново. Ключи из старого генератора можно
перенести в список vault_spa_clients, если они имеют требуемую длину.
Часы клиента и сервера должны быть синхронизированы.

## TTL и отзыв доступа

TTL контролирует **новые соединения**. nft NAT выбирает маршрут при первом
пакете соединения: уже открытые SSH/WebSocket/HTTP keepalive могут пережить TTL.
Соединение, попавшее на заглушку до SPA, также может оставаться на ней после
SPA: откройте новое TCP-соединение. Это поведение conntrack, не ошибка UI.

Для немедленного отзыва ключа удалите клиента из Vault и запустите Ansible;
перезагрузка firewall очищает leases. Если требуется прервать и активные
соединения конкретного IPv4, установите `conntrack` и выполните из rescue SSH:

```bash
sudo nft delete element inet spa_gate trusted_v4 '{ 198.51.100.20 }'
sudo conntrack -D -s 198.51.100.20
```

Удаление conntrack не завершает все протоколы одинаково; для строгого отзыва
используйте временный drop источника до established и проверьте снаружи.
Не выполняйте это для своего единственного административного соединения.
После reboot, применения firewall или рестарта proxy требуется новая SPA.
Остановка fwknop не удаляет leases, но ядро всё равно завершит их TTL.

## Логи и состояние

Nginx UI показывает nginx access/error logs, сайты, сертификаты и состояние
nginx. Включите штатную ротацию логов в настройках UI. Файлы постоянны в
`/opt/spa-proxy/logs`; stub-access.log отделён от обычного access.log.
Docker stdout ограничен 3 × 10 MB. Пример nginx UI logrotate необходимо
проверить и для stub-access.log; при отсутствии включить файл в шаблон ротации.

fwknop и nftables — хостовые компоненты, Nginx UI не является их панелью.
Для них используются SSH и journal (не заявляется управление SPA через UI):

```bash
sudo systemctl status spa-gate spa-fwknop spa-proxy
sudo journalctl -u spa-fwknop -b --no-pager
sudo journalctl -t fwknopd -b --no-pager
sudo journalctl -u spa-proxy -b --no-pager
sudo nft list set inet spa_gate trusted_v4
sudo nft list table inet spa_gate
sudo docker logs --tail 100 spa-nginx-ui
sudo docker exec spa-nginx-ui nginx -t
```

fwknop пишет также в syslog; при установленном rsyslog ищите fwknopd в
`/var/log/syslog`. Пустой `journalctl -u` не доказывает отсутствие событий —
проверьте syslog identifier. Пакетный debug включайте временно.

## Аварийный доступ

Rescue CIDR даёт только SSH и не открывает сайты. Держите две SSH-сессии при
первом запуске и проверяйте **новое** соединение после применения firewall.
Существующая сессия может работать благодаря conntrack и маскировать ошибку.
При смене провайдера/внешнего IP обновляйте rescue заранее.

Через консоль провайдера можно временно разрешить конкретный адрес:

```bash
sudo nft insert rule inet spa_gate input ip saddr 198.51.100.20 tcp dport 22 accept
```

Для IPv6 используйте `ip6 saddr`. Затем внесите адрес в Ansible, иначе изменение
исчезнет при следующем reload. Последний вариант — сначала остановить proxy,
затем удалить **только нашу** таблицу:

```bash
sudo systemctl stop spa-proxy
sudo nft delete table inet spa_gate
```

Это снимает защиту с оставшихся локальных сервисов; используйте консоль и
provider firewall. Не выполняйте `flush ruleset`.

UFW, firewalld, другие nft input chains и provider firewall могут дополнительно
блокировать трафик: accept нашей таблицы не отменяет чужой drop. Playbook не
отключает и не стирает чужие правила. Согласуйте их на чистом сервере заранее.

## Backup и обновление

Сохраняйте зашифрованный Vault, inventory и `/opt/spa-proxy` целиком.
Для согласованной копии SQLite и сертификатов остановите spa-proxy на время
архивации, затем запустите снова. Backup содержит private keys и DNS tokens;
храните зашифрованно с доступом только администратора. На новом сервере
восстановите каталоги с правами, затем примените Ansible с тем же образом.

Обновление образа контролируется через `spa_nginx_ui_image` и Ansible.
После смены digest Compose изменится и service перезапустится. При `latest`
сам pull не гарантирует restart: выполните `systemctl restart spa-proxy` после
backup. UI self-update внутри контейнера не заменяет обновление образа и может
исчезнуть при recreate. Systemd контролирует жизненный цикл контейнера;
ручной docker compose up в обход systemd не является штатным запуском.

RAM/CPU лимиты намеренно не навязаны: они могут ломать анализ логов и другие
функции UI. Лёгкость достигается отсутствием Certbot, БД-сервера, агента
мониторинга и второго nginx. Фактическое потребление зависит от версии UI,
трафика, индексации логов и включённых плагинов.
