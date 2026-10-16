# HerokuSafe 2.2.0

Telegram userbot based on [Heroku](https://github.com/Heroku-userbot/Heroku),
[Hikka](https://github.com/hikariatama/Hikka) and HerokuTL/Telethon.
This fork does not automatically trust future changes made by the original maintainer.

[Русский](README_RU.md) · [Security policy](SAFETY.md) · [Changelog](CHANGELOG.md)

## Install

Python 3.10+ and your own Telegram API credentials are required.
Prefer an unprivileged Linux user. On Windows use WSL, or run Python directly.

```bash
git clone https://github.com/qhozek/quiet-lumen-lekq.git Heroku
cd Heroku
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m heroku
```

Alternatively, download and inspect this repository's `install.sh`, then run `bash install.sh`.
Do not use the original project's installer for HerokuSafe.

## Update

Core updates come only from `qhozek/quiet-lumen-lekq`, branch `master`.
Update notifications are enabled by default; automatic installation is disabled by default.
Use `.update` to confirm an update. Updates never reset local changes or silently change origin.

Existing 2.1.0 installations will see the normal prompt after this release is published **only if**
their `origin` already points here, notifications are enabled, and their bot is online and working.
An installation pointing at the original project must first be migrated manually; changing files here
cannot alter a running installation's remote. Check `git remote get-url origin`.

Before migration stop the bot and make a private backup. Check local modifications, then set:

```bash
git remote set-url origin https://github.com/qhozek/quiet-lumen-lekq.git
git pull --ff-only origin master
```

If Git refuses because the histories differ, do not force-reset: install a fresh checkout and migrate
only reviewed private data/modules. Never upload session files, tokens or account databases.

### Docker

`docker compose build` builds the checked-out code, never the original repository.
`docker compose run --rm worker` performs interactive setup; then `docker compose up -d` runs it.
The `/data` volume contains private data, application code is in `/opt/HerokuSafe`.
Update the checkout, rebuild the image, and recreate the container. In-container Git updates are disabled.
Existing volumes are not erased; stop old containers before migrating.

## Security model

- No upstream allow-list, forced branch switch/logout, announcements or support-channel join prompts.
- Core updates are limited to this fork and use fast-forward-only merges.
- Installed URL modules use approved per-account local copies. Changed code needs confirmation;
  old "always update" grants are ignored. If no approved copy exists, reinstall explicitly with `.dlmod`.
- Imported libraries are cached locally, not refreshed on restart (`refresh=True` is explicit).
- API protection is enabled by default; HTTPS downloads, redaction and private/atomic writes are retained.
- **No sandbox:** modules you install can access your session and server. Review them before installing.
- HerokuTL is pinned to 2.2.0, but dependency pinning and code review are not proof of absolute safety.

Run regression tests with `python -m pip install pytest` and `python -m pytest tests -q`.
Tests do not need an account or contact Telegram.

## License / provenance

AGPL-3.0; see [LICENSE](LICENSE). Original copyright and license headers are preserved.
Ported upstream snapshot: `19f4a8f82159497d2f67e1fcbea8cab4249b3346` (2.2.0).
Original authors include Dan Gazizullin (Hikka), Codrago / Heroku contributors, and Lonami (Telethon).
Archived upstream docs are in `docs/` and are not this fork's installation instructions.
