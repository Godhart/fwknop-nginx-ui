#!/usr/bin/env python3
"""Применить только SPA таблицу в nftables одной транзакцией.

Не выполняет `flush ruleset`: не удаляет чужие таблицы (Docker/iptables).
Если таблица существует, она заменяется в ОДНОЙ nft транзакции. Новая
таблица содержит пустой trusted_v4: после изменения конфигурации
клиентам нужно повторить SPA, что является безопасным отказом.

При ошибке nft не должен частично применять правила (транзакционность).
Проверяйте с реальной версией nftables перед первым production rollout.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

CONFIG = pathlib.Path('/etc/spa-gate/spa-gate.nft')
NFT = '/usr/sbin/nft'


def make_batch(config_text: str, table_present: bool) -> str:
    return ('delete table inet spa_gate\n' if table_present else '') + config_text + '\n'


def main() -> int:
    if not CONFIG.is_file():
        print('spa-gate-apply: config not found', file=sys.stderr)
        return 2
    existing = subprocess.run([NFT, 'list', 'table', 'inet', 'spa_gate'],
                              text=True, capture_output=True)
    # ENOENT ожидаем на первом развёртывании; другие ошибки тоже проявятся
    # при попытке применить nft -f ниже.
    batch = make_batch(CONFIG.read_text(encoding='utf-8'), existing.returncode == 0)
    result = subprocess.run([NFT, '-f', '-'], input=batch,
                            text=True, capture_output=True)
    if result.returncode:
        print('spa-gate-apply: ' + result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
