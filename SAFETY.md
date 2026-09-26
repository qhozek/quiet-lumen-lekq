# herokusafe — что поменяно и почему

Скопия `coddrago/Heroku` без `.git` (оторвана от апстрима, `git remote` чужого нет).
Смысл патчей: чужой пуш / чужая ссылка не должны **молча** выполняться у тебя.
От уже украденной сессии и от модуля, который ты **сам руками** поставил, код не спасет —
для этого чеклист ниже.

## Патчи

1. `heroku/main.py` — `_main()`, `amain_wrapper()`
   Было: при каждом старте декодировался скрытый URL
   `raw.githubusercontent.com/coddrago/modules-web/.../allowed_ids.txt`,
   юзербот ходил туда по сети и тащил список id.
   Стало: phone-home вырезан полностью, `amain_wrapper(client)` без сетевых запросов.

2. `heroku/modules/updater.py` — `poller_announcement()`
   Было: каждые 60 сек тянул `coddrago/assets .../announcment.txt` и слал его
   тебе в личку через инлайн-бота (чужой текст у тебя в акке).
   Стало: `autostart=False` + `return`, но-оп.

3. `heroku/modules/loader.py` — `_update_modules()` + новый конфиг `autoupdate_modules`
   Было: на **каждый рестарт** молча перекачивал ВСЕ внешние модули
   (`download_and_install(mod)` для каждого из `loaded_modules`).
   Чужой пуш в modules-репо = RCE после рестарта.
   Стало: новый `ConfigValue("autoupdate_modules", False)`.
   По умолчанию перекачки нет, только лог. Обновление — руками через `.dlmod`
   или `.config Loader autoupdate_modules=True`.

4. `heroku/modules/api_protection.py` — `client_ready()`, `disable_protection`
   Было: `disable_protection` default `True` (= защита ВЫКЛ), а
   `forbid_constructors(joinChannel/importChatInvite)` применялся только
   после ручной смены конфига. Модуль мог молча джойнить чаты.
   Стало: default `False` (= защита ВКЛ), запрет применяется сразу в `client_ready()`.

5. `heroku/modules/quickstart.py` — `client_ready()`
   Было: `request_join("heroku_talks", ...)` при старте.
   Стало: no-op, только лог. Вступай руками, если надо.

## Апстрим: ZetGoHack/Heroku (2026-09-26)

Оригинал переехал к новому мейнтейнеру. Проверен их коммит
`87d855f "chore: replace coddrago/Heroku links with ZetGoHack/Heroku"`:
чистая замена ссылок `coddrago/Heroku` → `ZetGoHack/Heroku` (138+/138-),
новых бэкдоров/сливов нет. Но все старые рискованные механизмы там
на месте (phone-home, анонсы, перекачка модулей) — у нас они по-прежнему
вырезаны/выключены (см. выше).

Перенесено к нам (только смена origin, без ослабления защиты):
- `updater.py`: `GIT_ORIGIN_URL` и проверка версии → `ZetGoHack/Heroku`,
  ссылки compare → `ZetGoHack/Heroku`
- `main.py`, `utils/git.py`, `test.py`, `inline_stuff.py`,
  `token_obtainment.py`: ссылки на коммиты/GitHub → `ZetGoHack/Heroku`
- `Dockerfile`: clone → `ZetGoHack/Heroku`

НЕ переносилось: их phone-home, их анонсы, их docker-workflow.
`MODULES_REPO` и картинки `coddrago/assets` не менялись ни у них, ни у нас.

## Что НЕ закрыто (важно)

- `.dlmod <url>`, `.loadmod` (файлом), `.presets` — это произвольный Python,
  он всегда имеет полный доступ к сессии. Ставь только свое/проверенное.
  Пресеты в `heroku/modules/presets.py` (`PRESETS`) ссылаются на
  `mods.codrago.life`, `mods.kok.gay`, `github.com/amm1edev/...` — чужие хосты.
- Если сессия уже ушла раньше (файл `sessions/heroku-*.session`,
  `StringSession.save()`, `config.json`, `bot_token`), патчи не помогут —
  у атакующего независимый клиент. Надо убить сессии (см. ниже).
- Если его id уже в owners/sgroups/tsec — он управляет твоим ботом сообщениями.
  Проверь `.ownerlist`, `.sgroups`.

## Чеклист после копирования

1. Telegram > Настройки > Устройства — завершить чужие сессии.
2. BotFather — `/revoke` для инлайн-бота, 2FA/облачный пароль — сменить.
3. Старт с чистого: новые `config.json`, `sessions/`, не тащить старые
   `config-*.json` / `loaded_modules` вслепую.
4. `git init`, свой remote, в `.config Updater` → `GIT_ORIGIN_URL` на свой форк,
   `autoupdate=False`. В `.config Loader` проверь `MODULES_REPO` / `ADDITIONAL_REPOS`.
5. Первый рестарт при подозрениях: `.restart --secure-boot` (без внешних модулей),
   дальше `.unloadmod` / `.clearmodules`, чистка `.ownerlist` / `.sgroups`.
6. `.api_fw_protection` должен быть ON (теперь по умолчанию, проверь).
