#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ждать в cowork-сессии новое ГЛАВНОЕ сообщение после заданного seq.

Использование:
    watch_after.py <cse> [seq] [--interval 90] [--cycles 30]

Печатает найденный ответ и выходит 0; по таймауту — код 2.
Запускать фоном (с уведомлением при завершении).
ВАЖНО: seq сравнивается численно — строковое сравнение ('10017' < '9474')
молча пропускает ответы после 9999.
"""
import json
import os
import subprocess
import sys
import time


def extract_text(pl):
    m = pl.get('message') or {}
    c = m.get('content')
    t = ''
    if isinstance(c, str):
        t = c
    elif isinstance(c, list):
        for b in c:
            if isinstance(b, dict) and b.get('type') == 'text':
                t += b.get('text', '')
    if not t and isinstance(pl.get('result'), str):
        t = pl['result']
    return t


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    cse = args[0]
    if not cse.startswith('cse_'):
        cse = 'cse_' + cse
    seq0 = 0
    if len(args) > 1 and args[1].lstrip('-').isdigit():
        seq0 = int(args[1])
    interval = int(args[args.index('--interval') + 1]) if '--interval' in args else 90
    cycles = int(args[args.index('--cycles') + 1]) if '--cycles' in args else 30
    cfg = os.environ.get('COWORK_CFG',
                         os.path.expanduser('~/.config/cowork-bridge/curlrc'))
    url = 'https://claude.ai/v1/code/sessions/%s/events?limit=25' % cse

    for i in range(cycles):
        r = subprocess.run(['curl', '-sS', '--compressed', '-m', '60', '-K', cfg,
                            '-o', '/tmp/._watch_events.json', '-w', '%{http_code}', url],
                           capture_output=True, text=True)
        if r.stdout.strip() == '200':
            try:
                d = json.load(open('/tmp/._watch_events.json', encoding='utf-8'))
                evs = d.get('data') or []
                newest = int(evs[0].get('sequence_num') or 0) if evs else 0
                for e in evs:
                    sn = int(e.get('sequence_num') or 0)
                    if sn <= seq0:
                        continue
                    pl = e.get('payload') or {}
                    if 'agent_id' in pl:
                        continue
                    if e.get('event_type') not in ('assistant', 'result'):
                        continue
                    t = extract_text(pl)
                    if t.strip():
                        print('=== NEW (seq %d, newest %d) ===' % (sn, newest))
                        print(t[:4000])
                        print('[[[END]]]')
                        sys.exit(0)
                print('цикл %d: newest=%d — тихо' % (i, newest))
            except Exception as ex:
                print('ошибка:', ex)
        else:
            print('http:', r.stdout.strip())
        time.sleep(interval)

    print('== таймаут: нового главного сообщения нет ==')
    sys.exit(2)


if __name__ == '__main__':
    main()
