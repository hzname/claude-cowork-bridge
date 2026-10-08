#!/usr/bin/env python3
"""Полный выкач cowork-сессии Claude Desktop (cse_…) через claude.ai API.

Проверено 2026-10-06: Claude Desktop 2.19675.1.0 (MSIX), Chromium 152, WSL.
Требования: Windows+WSL (powershell.exe для DPAPI), python `cryptography`, curl.

Использование:
    python3 cowork_pull.py cse_XXXXXXXXXXXXXXXXXXXXXXXX [--out DIR] [--roaming DIR]

Авторизацию читает из локального хранилища Claude Desktop (только с согласия владельца!):
Local State -> os_crypt-ключ (DPAPI) -> Network/Cookies (AES-GCM, срез 32-байтного префикса).
Секреты не печатаются. Результат: DIR/cowork_all_events.jsonl(.gz), DIR/cowork_transcript.md,
DIR/cowork_session_import.jsonl -> импорт: hermes sessions import --from claude <jsonl>.
"""
import argparse
import base64
import datetime
import glob
import gzip
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid
from collections import Counter

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Claude/2.19675.0 Chrome/152.0.7977.130 Electron/44.4.3 Safari/537.36")
WRAPPER_PREFIXES = ("<system-reminder", "<artifact-view-context",
                    "<artifact-content-authored-by-others", "<local-command", "<command-",
                    "Base directory for this skill:", "Caveat:")


def find_roaming():
    hits = sorted(glob.glob("/mnt/c/Users/*/AppData/Local/Packages/Claude_*/LocalCache/Roaming/Claude"))
    if not hits:
        sys.exit("Не найден каталог Claude Desktop LocalCache/Roaming/Claude")
    return hits[0]


def win_path(p):
    return p.replace("/mnt/c/", "C:\\").replace("/", "\\")


def unseal_key(roaming):
    ls = json.load(open(os.path.join(roaming, "Local State"), encoding="utf-8"))
    ek = ls["os_crypt"]["encrypted_key"]
    m = re.match(r"(/mnt/c/Users/[^/]+)", roaming)
    tmp = os.path.join(m.group(1), "AppData/Local/Temp/cowork_pull")
    os.makedirs(tmp, exist_ok=True)
    kfile = os.path.join(tmp, "ls_key_b64.txt")
    with open(kfile, "w") as f:
        f.write(ek)
    ps1 = os.path.join(tmp, "unseal.ps1")
    with open(ps1, "w") as f:
        f.write(
            "Add-Type -AssemblyName System.Security\n"
            "$b64=(Get-Content -Raw '" + win_path(kfile) + "').Trim()\n"
            "$b=[Convert]::FromBase64String($b64)\n"
            "$blob=New-Object byte[] ($b.Length-5)\n"
            "[Array]::Copy($b,5,$blob,0,$blob.Length)\n"
            "$p=[System.Security.Cryptography.ProtectedData]::Unprotect($blob,$null,"
            "[System.Security.Cryptography.DataProtectionScope]::CurrentUser)\n"
            "[Convert]::ToBase64String($p) | Set-Content -NoNewline -Encoding ascii '" +
            win_path(os.path.join(tmp, "os_key_b64.txt")) + "'\n")
    subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", win_path(ps1)],
                   check=True, capture_output=True)
    key = base64.b64decode(open(os.path.join(tmp, "os_key_b64.txt")).read().strip())
    assert len(key) == 32, "не 32-байтный ключ"
    return key


def decrypt_cookies(roaming, key):
    src = os.path.join(roaming, "Network", "Cookies")
    tmp_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies_copy.sqlite")
    shutil.copy(src, tmp_db)
    cookies = {}
    con = sqlite3.connect(tmp_db)
    try:
        for host, name, ev in con.execute(
                "SELECT host_key,name,encrypted_value FROM cookies WHERE host_key LIKE '%claude.ai%'"):
            try:
                if ev[:3] != b"v10":
                    continue
                val = AESGCM(key).decrypt(ev[3:15], ev[15:], None)[32:].decode("utf-8")
                if all(0x20 < ord(c) < 0x7F and c not in '";\\' for c in val):
                    cookies[name] = val
            except Exception:
                pass
    finally:
        con.close()
        try:
            os.remove(tmp_db)
        except OSError:
            pass
    if not cookies:
        sys.exit("Cookies не расшифровались")
    return cookies


def curlrc(out_dir, cse, cookies):
    path = os.path.join(out_dir, ".curlrc")
    cook = "; ".join(f"{k}={v}" for k, v in cookies.items())
    with open(path, "w") as f:
        f.write('user-agent = "' + UA + '"\n'
                'header = "Cookie: ' + cook + '"\n'
                'header = "Accept: */*"\n'
                'header = "Origin: https://claude.ai"\n'
                'header = "Referer: https://claude.ai/cowork/' + cse + '"\n'
                'header = "anthropic-version: 2023-06-01"\n')
    os.chmod(path, 0o600)
    return path


def fetch_events(out_dir, cse, cfg):
    base = "https://claude.ai/v1/code/sessions/" + cse + "/events"
    evdir = os.path.join(out_dir, "events")
    os.makedirs(evdir, exist_ok=True)
    all_ev, cursor, page = {}, None, 0
    while page < 60:
        url = base + "?limit=500" + (("&cursor=" + cursor) if cursor else "")
        out = os.path.join(evdir, "page_%03d.json" % page)
        r = subprocess.run(["curl", "-sS", "--compressed", "-m", "120", "-K", cfg, "-o", out,
                            "-w", "%{http_code} %{size_download}", url],
                           capture_output=True, text=True, timeout=180)
        try:
            d = json.load(open(out))
        except Exception as ex:
            print("  page %d: parse fail: %s (%s)" % (page, ex, r.stdout.strip()))
            break
        evs = d.get("data", [])
        print("  page %d: %s events=%d" % (page, r.stdout.strip(), len(evs)))
        if not evs:
            break
        for e in evs:
            all_ev[int(e["sequence_num"])] = e
        seqs = [int(e["sequence_num"]) for e in evs]
        nc = d.get("next_cursor")
        if not nc or (cursor and str(nc) == str(cursor)) or min(seqs) <= 1:
            break
        cursor = str(nc)
        page += 1
    seqs = sorted(all_ev)
    if not seqs:
        sys.exit("События не получены (проверь cookie/заголовки)")
    print("  Всего событий: %d (seq %d..%d)" % (len(seqs), seqs[0], seqs[-1]))
    path = os.path.join(out_dir, "cowork_all_events.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for s in seqs:
            f.write(json.dumps(all_ev[s], ensure_ascii=False) + "\n")
    with open(path, "rb") as fi, gzip.open(path + ".gz", "wb", compresslevel=6) as fo:
        shutil.copyfileobj(fi, fo)
    return [all_ev[s] for s in seqs]


def build_turns(events):
    def utext(e):
        c = (e.get("payload") or {}).get("message", {}).get("content")
        if isinstance(c, list):
            if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
                return None
            c = "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
        if not isinstance(c, str) or not c.strip():
            return None
        c = c.strip()
        if c.startswith(WRAPPER_PREFIXES):
            return None
        pl = e.get("payload") or {}
        if pl.get("isSynthetic") or pl.get("synthetic_message") or pl.get("silent_resend_of"):
            return None
        return "[изображение]" if c.startswith("[Image:") else c

    uprompts = []
    for e in events:
        if e["event_type"] != "user":
            continue
        if (e.get("payload") or {}).get("parent_tool_use_id") is not None:
            continue
        t = utext(e)
        if t:
            uprompts.append((int(e["sequence_num"]), t, e))
    results = [e for e in events if e["event_type"] == "result"]
    asst = [e for e in events if e["event_type"] == "assistant"]

    turns, prev_seq = [], 0
    for r in results:
        rseq = int(r["sequence_num"])
        for useq, txt, ue in uprompts:
            if prev_seq < useq < rseq:
                turns.append(["user", txt, ue])
        tc, tblocks = Counter(), []
        for e in asst:
            s = int(e["sequence_num"])
            if not (prev_seq < s <= rseq):
                continue
            if (e.get("payload") or {}).get("parent_tool_use_id") is not None:
                continue
            for b in e["payload"]["message"]["content"]:
                if b.get("type") == "tool_use":
                    tc[b.get("name") or "?"] += 1
                elif b.get("type") == "text" and (b.get("text") or "").strip():
                    tblocks.append(b["text"].strip())
        rtext = (r["payload"].get("result") or "").strip() or "\n\n".join(tblocks)
        txt = rtext or "(без текстового ответа)"
        if tc:
            txt += "\n\n🔧 Вызваны инструменты: " + ", ".join("%s×%d" % (n, c) for n, c in tc.most_common())
        turns.append(["assistant", txt, r, rtext == ""])
        prev_seq = rseq
    for useq, txt, ue in uprompts:
        if useq > prev_seq:
            turns.append(["user", txt, ue])

    clean = []
    for i, t in enumerate(turns):
        if len(t) > 3 and t[3] and i + 1 < len(turns) and turns[i + 1][0] == "assistant":
            continue
        clean.append(t)
    merged = []
    for t in clean:
        if merged and merged[-1][0] == t[0]:
            merged[-1][1] += "\n\n" + t[1]
        else:
            merged.append([t[0], t[1], t[2]])
    return merged


def write_outputs(out_dir, cse, merged):
    msk = datetime.timezone(datetime.timedelta(hours=3))

    def fmt(ts):
        try:
            return (datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    .astimezone(msk).strftime("%d.%m.%Y %H:%M"))
        except Exception:
            return ts or ""

    md = ["# Переписка Cowork-сессии", "", "- Сессия: `%s`" % cse,
          "- Источник: Claude Desktop → Cowork (полный выкач через API)", ""]
    for i, (role, txt, e) in enumerate(merged, 1):
        who = "Пользователь" if role == "user" else "Claude"
        md += ["## %d. %s — %s" % (i, who, fmt(e.get("created_at"))), "", txt, ""]
    open(os.path.join(out_dir, "cowork_transcript.md"), "w", encoding="utf-8").write("\n".join(md))

    imp = os.path.join(out_dir, "cowork_session_import.jsonl")
    with open(imp, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "summary", "summary": "Cowork " + cse}, ensure_ascii=False) + "\n")
        for role, txt, e in merged:
            rec = {"type": role, "uuid": str(uuid.uuid4()), "timestamp": e.get("created_at"),
                   "sessionId": cse, "cwd": "/home/claude"}
            rec["message"] = ({"role": "user", "content": txt} if role == "user"
                              else {"role": "assistant", "content": [{"type": "text", "text": txt}]})
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return imp


def main():
    ap = argparse.ArgumentParser(description="Полный выкач cowork-сессии Claude Desktop")
    ap.add_argument("cse")
    ap.add_argument("--roaming", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    roaming = a.roaming or find_roaming()
    out_dir = a.out or os.path.join(os.getcwd(), "cowork-import-" + a.cse[-6:])
    os.makedirs(out_dir, exist_ok=True)
    print("roaming: %s\nout: %s" % (roaming, out_dir))
    key = unseal_key(roaming)
    cookies = decrypt_cookies(roaming, key)
    cfg = curlrc(out_dir, a.cse, cookies)
    events = fetch_events(out_dir, a.cse, cfg)
    merged = build_turns(events)
    imp = write_outputs(out_dir, a.cse, merged)
    print("реплик: %d (user %d / assistant %d)" % (
        len(merged), sum(1 for t in merged if t[0] == "user"), sum(1 for t in merged if t[0] == "assistant")))
    print("импорт: hermes sessions import --from claude %s" % imp)


if __name__ == "__main__":
    main()
