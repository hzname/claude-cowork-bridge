#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Отправка текстового сообщения (задачи) в cowork-сессию Claude.

Использование:
    cowork_post.py <cse_или_короткий_ID> <файл-с-текстом | ->

Конфиг: env COWORK_CFG (по умолчанию ~/.config/cowork-bridge/curlrc) — curl-конфиг
с cookie-заголовками claude.ai (готовится скриптом cowork_pull.py).

Успешный ответ: {"results":[{"sequence_num":"…"}]}. Повторная отправка с тем же
uuid отсекается как дубликат — uuid генерируется заново на каждый запуск.
Сообщение, отправленное в активный лимит, может быть съедено — после отправки
убедитесь, что sequence_num появился в ленте (watch_after.py).
"""
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    cse = sys.argv[1]
    if not cse.startswith('cse_'):
        cse = 'cse_' + cse
    if sys.argv[2] == '-':
        text = sys.stdin.read()
    else:
        text = Path(sys.argv[2]).read_text(encoding='utf-8')
    cfg = os.environ.get('COWORK_CFG',
                         os.path.expanduser('~/.config/cowork-bridge/curlrc'))

    body = {'events': [{'event_type': 'user',
                        'payload': {'type': 'user',
                                    'uuid': str(uuid.uuid4()),
                                    'message': {'role': 'user', 'content': text},
                                    'client_platform': 'desktop_app'}}]}
    body_path = '/tmp/._cowork_post_body.json'
    resp_path = '/tmp/._cowork_post_resp.json'
    Path(body_path).write_text(json.dumps(body, ensure_ascii=False), encoding='utf-8')

    url = 'https://claude.ai/v1/code/sessions/%s/events' % cse
    r = subprocess.run(['curl', '-sS', '--compressed', '-m', '90', '-K', cfg,
                        '-X', 'POST', '-H', 'Content-Type: application/json',
                        '-o', resp_path, '--data-binary', '@' + body_path, url],
                       capture_output=True, text=True, timeout=150)
    print('curl rc:', r.returncode, r.stdout.strip()[:200])
    try:
        d = json.loads(Path(resp_path).read_text(encoding='utf-8'))
        print('resp:', json.dumps(d, ensure_ascii=False)[:400])
    except Exception as e:  # noqa
        print('resp read fail:', e, Path(resp_path).read_bytes()[:300])


if __name__ == '__main__':
    main()
