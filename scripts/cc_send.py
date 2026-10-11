#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Отправить сообщение в живую сессию Claude Code через её inbox-сокет.

Использование: python3 cc_send.py <socket_path> <session_id> <файл_с_текстом>
Протокол: newline-delimited JSON (msgV=1); после отправки — half-close (SHUT_WR).
"""
import json
import socket
import sys
import uuid

sock_path, session_id, text_path = sys.argv[1], sys.argv[2], sys.argv[3]
with open(text_path, encoding='utf-8') as f:
    text = f.read().rstrip('\n')

frame = {
    "msgV": 1,
    "msg_id": str(uuid.uuid4()),
    "type": "user",
    "message": {"role": "user", "content": text},
    "priority": "next",
    "session_id": session_id,
}
line = json.dumps(frame, ensure_ascii=False) + "\n"

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(10)
s.connect(sock_path)
s.sendall(line.encode('utf-8'))
s.shutdown(socket.SHUT_WR)
s.close()
print('sent: %s -> %s (session %s)' % (frame['msg_id'], sock_path, session_id))
