# claude-cowork-bridge

Скилл для Hermes Agent — все действия с сессиями Claude:
cowork-сессия (claude.ai, `cse_…`) — поставить задачу, дождаться ответа,
забрать артефакты, проверить результат; живая локальная сессия Claude Code —
подключиться и доставить сообщение (inbox-сокет); импорт сессий в Hermes
и разбор хранилищ Claude (форензика).

Документация скилла — русская (`SKILL.md` + `references/`).

## Состав

| Файл | Назначение |
|---|---|
| `SKILL.md` | модель работы, приёмка, импорт, питфоллы — основной документ |
| `references/api.md` | эндпоинты claude.ai, структура событий, лимиты |
| `references/claude-stores-map.md` | карта хранилищ Claude Code/Desktop, записи bridge, формат V8 |
| `scripts/cowork_post.py` | отправить сообщение (задачу) в сессию |
| `scripts/watch_after.py` | ждать новое главное сообщение (окно 500, числовое сравнение seq) |
| `scripts/cowork_get.py` | скачать файл из среды сессии |
| `scripts/cowork_pull.py` | выкачать cookies из Claude Desktop + полный экспорт ленты |
| `scripts/v8_probe.js` | дамп V8-значений из блобов IndexedDB (форензика) |
| `scripts/cc_sessions.py` | список живых сессий Claude Code проекта (ручной выбор, если их несколько) |
| `scripts/cc_send.py` | доставить сообщение в живую сессию Claude Code (inbox-сокет) |
| `scripts/cc_peek.py` | шапка и хвост лога сессии (проверка доставки) |
| `scripts/cc_search.py` | поиск по тексту сообщений лога сессии |

## Быстрый старт

Требования: Python 3.9+, `curl`, `pip install cryptography`; для извлечения
cookies — Windows с Claude Desktop (скрипт использует `powershell.exe`).

```sh
# 1. Извлечь cookies и выкачать ленту (одноразово; секреты не печатаются)
python3 scripts/cowork_pull.py cse_XXXXXXXX --out ./cowork_out
#    → ./cowork_out/.curlrc — готовый curl-конфиг с cookie-заголовками (chmod 600)

# 2. Указать конфиг остальным скриптам
export COWORK_CFG=./cowork_out/.curlrc

# 3. Отправить задачу
python3 scripts/cowork_post.py cse_XXXXXXXX task.txt

# 4. Дождаться ответа (запускать фоном; сравнение seq — числовое)
python3 scripts/watch_after.py cse_XXXXXXXX 12345

# 5. Забрать артефакт
python3 scripts/cowork_get.py cse_XXXXXXXX /mnt/user-data/outputs/result.zip ./result.zip
```

Доставка в живую сессию Claude Code (локально, inbox-сокет):

```sh
# живые сессии проекта — выбрать вручную, если их несколько
python3 scripts/cc_sessions.py ~/robot-dog

# доставить сообщение (кадр: newline-JSON + half-close; ответ не придёт — канал односторонний)
python3 scripts/cc_send.py /run/user/1000/cc-socks/<pid>.sock <sessionId> context.txt
```

Импорт сессии в Hermes:

```sh
hermes sessions import --from claude session.jsonl
hermes --resume <полученный id>
```

## Питфоллы (полный список — в `SKILL.md`)

- `sequence_num` сравнивать только численно: строковое сравнение молча
  пропускает ответы после 9999 (`'10017' < '9474'`).
- Ответы живут в главной ветке (события без `payload.agent_id`);
  события под-агентов — шум.
- Лимиты API: `limit ≤ 500`, файл ≤ 25 МиБ, `rate_limit_event` — сообщение
  может «съесться» в активный лимит; заголовок `anthropic-version` обязателен.
- Файл **в** сессию публичным API не кладётся: вложение добавляет только
  владелец через интерфейс Claude Desktop.
- Результат сессии — самоотчёт; артефакты проверять независимо
  (диффы, прогоны), а не доверять описанию.
- Claude Code: pid и сокет меняются при перезапуске сессии; `session_id`
  кадра обязан совпадать с получателем (иначе молчаливый дроп); при
  нескольких сессиях проекта — выбор вручную (`cc_sessions.py`).
- Форензика: бинарные хранилища (LevelDB, IndexedDB) ищутся только
  `rg -a -uu` — без `-a` ложное «нигде нет»; данные Desktop — в
  `Packages/…/LocalCache`, не в `AppData/Roaming`.

## Установка как скилла Hermes

Скопировать каталог в `~/.hermes/skills/<категория>/claude-cowork-bridge/`
(либо использовать как обычный набор CLI-скриптов).

## Замечания

- Использовать только со своим аккаунтом и с согласия владельца аккаунта.
- API неофициальный (внутренний API Claude Desktop) и может меняться.

## Лицензия

MIT — см. `LICENSE`.

---

*A Hermes Agent skill + CLI tools for Claude sessions: a "cowork" session
(claude.ai `cse_…`) — post tasks, watch replies, download artifacts, verify
deliverables; live local Claude Code sessions (message over the inbox socket);
session import into Hermes and store forensics. Documents in Russian. MIT.*
