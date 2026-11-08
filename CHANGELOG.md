# 2.0.1

- Исправлен bootstrap nginx-ui.conf согласно WebSocket self-check Nginx UI.
- Forwarded proto/host сохраняются только на loopback UI proxy.
- Добавлена регрессионная проверка; существующие конфиги не перезаписываются.

# 2.0.0

- Новая dedicated reverse proxy архитектура, один Docker Nginx UI.
- Все сайты, сертификаты, ACME и nginx logs принадлежат UI.
- NAT неавторизованных HTTP и HTTPS на заглушку, включая IPv6.
- UI через SSH tunnel, защищён от прямого доступа даже после SPA.
- Отдельные клиентские ключи, IPv4 leases, TCP/UDP профили, bypass и rescue.
- Одноразовый bootstrap вместо перезаписи пользовательской конфигурации.
- Опциональный Docker, Ubuntu 24.04/26.04, ADR и тесты.
