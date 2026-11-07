# 2.0.0

- Новая dedicated reverse proxy архитектура, один Docker Nginx UI.
- Все сайты, сертификаты, ACME и nginx logs принадлежат UI.
- NAT неавторизованных HTTP и HTTPS на заглушку, включая IPv6.
- UI через SSH tunnel, защищён от прямого доступа даже после SPA.
- Отдельные клиентские ключи, IPv4 leases, TCP/UDP профили, bypass и rescue.
- Одноразовый bootstrap вместо перезаписи пользовательской конфигурации.
- Опциональный Docker, Ubuntu 24.04/26.04, ADR и тесты.
