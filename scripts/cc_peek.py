#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Показать шапку и хвост jsonl-сессии Claude Code.

Использование: python3 cc_peek.py <file.jsonl> [N] [maxchars]
"""
import json
import sys

path = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
maxchars = int(sys.argv[3]) if len(sys.argv) > 3 else 280

lines = []
with open(path, encoding='utf-8', errors='replace') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        lines.append(line)

print('file:', path)
print('lines:', len(lines))
for idx in (0, len(lines) - 1):
    try:
        d = json.loads(lines[idx])
        print('  edge[%d]: ts=%s type=%s cwd=%s' % (
            idx, (d.get('timestamp') or '')[:19], d.get('type'), d.get('cwd')))
    except Exception as e:
        print('  edge[%d]: parse error %s' % (idx, e))


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
            elif t == 'tool_result':
                parts.append('[tool_result]')
        return ' '.join(parts)
    return str(c)


print('--- last %d ---' % n)
for line in lines[-n:]:
    try:
        d = json.loads(line)
    except Exception:
        print('  (parse error)')
        continue
    ts = (d.get('timestamp') or '')[11:19]
    txt = text_of(d).replace('\n', ' ')
    print('---', ts, d.get('type', '?'), '|', txt[:maxchars])
