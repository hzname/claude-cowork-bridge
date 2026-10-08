#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скачивание файла из cowork-сессии Claude.

Использование:
    cowork_get.py <cse_или_короткий_ID> </mnt/user-data/…/путь> [выходной_файл]

Конфиг: env COWORK_CFG (по умолчанию ~/.config/cowork-bridge/curlrc).
Доступные корни: /mnt/user-data/outputs, /mnt/user-data/working,
/mnt/user-data/uploads, /mnt/user-data/mcp_spill; предел — 25 МиБ на файл.
"""
import base64
import json
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    cse = sys.argv[1]
    if not cse.startswith('cse_'):
        cse = 'cse_' + cse
    remote = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else Path(remote).name
    cfg = os.environ.get('COWORK_CFG',
                         os.path.expanduser('~/.config/cowork-bridge/curlrc'))

    url = 'https://claude.ai/v1/code/sessions/%s/file?path=%s' % (
        cse, urllib.parse.quote(remote, safe=''))
    resp = '/tmp/._cowork_get_resp.json'
    r = subprocess.run(['curl', '-sS', '--compressed', '-m', '300', '-K', cfg,
                        '-o', resp, '-w', '%{http_code}', url],
                       capture_output=True, text=True, timeout=320)
    print('HTTP', r.stdout.strip())
    if r.stdout.strip() != '200':
        print(Path(resp).read_bytes()[:300])
        sys.exit(1)
    data = base64.b64decode(json.loads(Path(resp).read_text(encoding='utf-8'))['content'])
    Path(out).write_bytes(data)
    print('сохранён: %s (%.1f КБ)' % (out, len(data) / 1e3))


if __name__ == '__main__':
    main()
