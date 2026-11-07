# Результаты сборки 2026-11-07

- Python unittest: 14/14 PASS.
- Ansible playbook syntax-check: PASS (ansible-core 2.21.6).
- Jinja2 strict render всех шаблонов: PASS (в составе unittest).
- Полное выполнение Ansible на localhost: не выполнено — runtime не позволил
  запустить внутренний RPC worker Ansible (`Local RPC server did not start`).
- Docker/nginx/nft kernel integration, Ubuntu 24.04/26.04 VM и ACME:
  не запускались. Приёмка описана в VALIDATION.md.

Образ с плавающим тегом latest не был скачан и не сертифицирован этой сборкой.
Перед эксплуатацией зафиксируйте digest после прохождения VM-проверок.
