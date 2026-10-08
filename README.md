# claude-cowork-bridge

Скилл для Hermes Agent — работа с cowork-сессией Claude (claude.ai, `cse_…`)
как со второй командой: поставить задачу, дождаться ответа, забрать артефакты,
проверить результат.

Документация скилла — русская (`SKILL.md` + `references/api.md`).

## Состав

| Файл | Назначение |
|---|---|
| `SKILL.md` | модель работы, приёмка, питфоллы — основной документ |
| `references/api.md` | эндпоинты claude.ai, структура событий, лимиты |
| `scripts/cowork_post.py` | отправить сообщение (задачу) в сессию |
| `scripts/watch_after.py` | ждать новое главное сообщение (числовое сравнение seq) |
| `scripts/cowork_get.py` | скачать файл из среды сессии |
| `scripts/cowork_pull.py` | выкачать cookies из Claude Desktop + полный экспорт ленты |

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

## Питфоллы (полный список — в `SKILL.md`)

- `sequence_num` сравнивать только численно: строковое сравнение молча
  пропускает ответы после 9999 (`'10017' < '9474'`).
- Ответы живут в главной ветке (события без `payload.agent_id`);
  события под-агентов — шум.
- Лимиты API: `limit ≤ 500`, файл ≤ 25 МиБ, `rate_limit_event` — сообщение
  может «съесться» в активный лимит.
- Файл **в** сессию публичным API не кладётся: вложение добавляет только
  владелец через интерфейс Claude Desktop.
- Результат сессии — самоотчёт; артефакты проверять независимо
  (диффы, прогоны), а не доверять описанию.

## Установка как скилла Hermes

Скопировать каталог в `~/.hermes/skills/<категория>/claude-cowork-bridge/`
(либо использовать как обычный набор CLI-скриптов).

## Замечания

- Использовать только со своим аккаунтом и с согласия владельца аккаунта.
- API неофициальный (внутренний API Claude Desktop) и может меняться.

## Лицензия

MIT — см. `LICENSE`.

---

*A Hermes Agent skill + CLI tools to drive a Claude "cowork" session
(claude.ai `cse_…`): post tasks, watch for replies, download artifacts,
verify deliverables. Documents in Russian. MIT.*
