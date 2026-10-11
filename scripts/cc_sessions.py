#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Список ЖИВЫХ сессий Claude Code для проекта — ручной выбор, если их несколько.

Использование: python3 cc_sessions.py <каталог проекта>
Отсеивает мёртвые pid (в т.ч. переиспользованные: сверка procStart с /proc/<pid>/stat)
и отсутствующие сокеты. Дальше:
  python3 cc_send.py <сокет> <sessionId> <файл-с-текстом>
"""
import glob
import json
import os
import sys
import time

cwd_filter = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()


def proc_alive(d):
    """pid жив И это тот самый процесс (procStart == starttime из /proc)."""
    pid = d.get('pid')
    if not pid or not os.path.exists('/proc/%s' % pid):
        return False
    try:
        starttime = open('/proc/%s/stat' % pid).read().split()[21]
    except Exception:
        return False
    ps = d.get('procStart')
    return (str(ps) == starttime) if ps else True


rows = []
for p in glob.glob(os.path.expanduser('~/.claude/sessions/*.json')):
    try:
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        continue
    if os.path.abspath(d.get('cwd') or '') != cwd_filter:
        continue
    sock = d.get('messagingSocketPath') or ''
    if not proc_alive(d) or not sock or not os.path.exists(sock):
        continue
    rows.append((d.get('startedAt') or 0, d.get('pid'), d.get('sessionId'),
                 d.get('name') or '?', d.get('status') or '?',
                 sock, d.get('version') or '?'))

rows.sort(reverse=True)
if not rows:
    print('живых сессий Claude Code для %s нет' % cwd_filter)
    sys.exit(1)

print('живые сессии Claude Code для %s:' % cwd_filter)
for started, pid, sid, name, status, sock, ver in rows:
    t = time.strftime('%d.%m %H:%M', time.localtime(started / 1000.0)) if started else '?'
    print('  pid=%-8s %s  «%s»  status=%s  v%s  старт %s' % (pid, sid, name, status, ver, t))
    print('      сокет: %s' % sock)
print()
print('Выбор — вручную (по имени/статусу; при неоднозначности спросить владельца). Отправка:')
print('  python3 cc_send.py <сокет> <sessionId> <файл-с-текстом>')
