#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Поиск по тексту сообщений jsonl-сессии Claude Code.

Использование: python3 cc_search.py <file.jsonl> <слово1> [слово2 ...]
Печатает: ts | type | первые 300 символов текста для сообщений,
где встречается любое из слов (регистронезависимо).
"""
import json
import sys

path = sys.argv[1]
words = [w.lower() for w in sys.argv[2:]]


def text_of(d):
    m = d.get('message') or {}
    c = m.get('content')
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for b in c:
            if not isinstance(b, dict):
                continue
            t = b.get('type')
            if t == 'text':
                parts.append(b.get('text', ''))
            elif t == 'tool_use':
                parts.append('[tool: %s]' % b.get('name'))
        return ' '.join(parts)
    return str(c)


shown = 0
with open(path, encoding='utf-8', errors='replace') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get('type') not in ('user', 'assistant'):
            continue
        txt = text_of(d)
        low = txt.lower()
        if any(w in low for w in words):
            ts = (d.get('timestamp') or '')[:19]
            print('=== %s %s' % (ts, d.get('type')))
            print(txt.replace('\n', ' ')[:300])
            shown += 1
print('(всего совпадений: %d)' % shown)
