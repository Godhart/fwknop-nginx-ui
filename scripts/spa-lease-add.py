#!/usr/bin/env python3
"""Добавить/продлить доверенный IPv4 после корректного SPA.

Этот код вызывается только fwknopd через CMD_CYCLE_OPEN.
Проверяет аргументы и НЕ запускает shell; адрес передается nft безопасно.
Постоянной базы разрешений нет: состояние и TTL хранятся в ядре.

Почему здесь нет CMD_CYCLE_CLOSE:
  - nftables самостоятельно удаляет просроченные IP;
  - если fwknopd перезапустится, lease по-прежнему истечет;
  - повторная SPA авторизация атомарно обновляет expires, а не создает
    дублирующиеся таймеры, которые могут удалить продленную запись.
"""
from __future__ import annotations

import ipaddress
import subprocess
import sys


def build_transaction(ip_string: str, ttl_string: str) -> str:
    """Вернуть одну атомарную nft транзакцию, валидируя входные данные."""
    try:
        addr = ipaddress.ip_address(ip_string)
        ttl = int(ttl_string)
    except ValueError as exc:
        raise ValueError("Недопустимый IP или TTL") from exc
    # UDP fwknopd в этом MVP работает только с IPv4 (AF_INET).
    if addr.version != 4 or addr.is_multicast or addr.is_unspecified:
        raise ValueError("Только корректные IPv4 источники")
    if not 30 <= ttl <= 3600:
        raise ValueError("TTL должен быть в диапазоне от 30 до 3600 сек")
    ip = str(addr)
    # Одна транзакция с add/delete/add: idempotent даже при первом вызове.
    # nftables wiki: обновление timeout элемента достигается удалением и
    # созданием заново. Команда `add` с существующим значением допустима.
    # В случае ошибки транзакция в целом отвергается; разрешений не появляется.
    return (
        f"add element inet spa_gate trusted_v4 {{ {ip} }}\n"
        f"delete element inet spa_gate trusted_v4 {{ {ip} }}\n"
        f"add element inet spa_gate trusted_v4 {{ {ip} timeout {ttl}s }}\n"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: spa-lease-add IPv4 TTL_SECONDS", file=sys.stderr)
        return 2
    try:
        transaction = build_transaction(argv[1], argv[2])
    except ValueError as exc:
        print(f"spa-lease-add: {exc}", file=sys.stderr)
        return 2
    result = subprocess.run(
        ["/usr/sbin/nft", "-f", "-"],
        input=transaction,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        print(f"spa-lease-add: nft rejected transaction: {result.stderr}", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
