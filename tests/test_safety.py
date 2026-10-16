import ast
import asyncio
import hashlib
import importlib
import os
import types
from pathlib import Path
from unittest.mock import AsyncMock

import git
import pytest

from conftest import MemoryDB
from heroku import _internal, main
from heroku._release import REPOSITORY_URL, is_safe_origin
from heroku.modules.api_protection import APIRatelimiterMod, CONSTRUCTORS
from heroku.modules.loader import LoaderMod
from heroku.modules.updater import UpdaterMod
from heroku.types import Module

ROOT = Path(__file__).resolve().parents[1]


def configured_loader(tmp_path):
    module = LoaderMod()
    module.tg_id = 123
    module.db = module._db = MemoryDB()
    module.allmodules = types.SimpleNamespace(secure_boot=False, modules=[])
    module.inline = types.SimpleNamespace(init_complete=True, _bot_client=object())
    module._modules_cache_dir = str(tmp_path / "approved")
    module._storage = types.SimpleNamespace(fetch=AsyncMock())
    return module


@pytest.mark.parametrize("url", [REPOSITORY_URL, REPOSITORY_URL + ".git"])
def test_safe_origin(url):
    assert is_safe_origin(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/Heroku-userbot/Heroku",
        "https://github.com/ZetGoHack/Heroku",
        "https://github.com/qhozek/quiet-lumen-lekq-other",
        "https://github.com.evil.test/qhozek/quiet-lumen-lekq",
        "https://user:password@github.com/qhozek/quiet-lumen-lekq",
        REPOSITORY_URL + "?redirect=elsewhere",
        "http://github.com/qhozek/quiet-lumen-lekq",
    ],
)
def test_other_origin_rejected(url):
    assert not is_safe_origin(url)


def test_updater_checks_actual_git_remote(tmp_path, monkeypatch):
    with git.Repo.init(tmp_path) as repo:
        path = tmp_path / "file"
        path.write_text("base")
        repo.index.add(["file"])
        actor = git.Actor("Test", "test@example.invalid")
        repo.index.commit("base", author=actor, committer=actor)
        repo.git.branch("-M", "master")
        origin = repo.create_remote(
            "origin", "https://github.com/Heroku-userbot/Heroku"
        )
        monkeypatch.setattr(
            "heroku.modules.updater.utils.get_base_dir",
            lambda: str(tmp_path / "heroku"),
        )
        with pytest.raises(RuntimeError, match="upstream/unknown"):
            UpdaterMod._safe_repo()
        origin.set_url(REPOSITORY_URL)
        with UpdaterMod._safe_repo() as checked:
            assert checked.active_branch.name == "master"
        repo.create_head("other").checkout()
        with pytest.raises(RuntimeError, match="master branch"):
            UpdaterMod._safe_repo()


def test_restart_never_downloads_missing_module(tmp_path):
    module = configured_loader(tmp_path)
    module.load_module = AsyncMock()
    assert not asyncio.run(
        module._load_cached_module("https://example.invalid/test.py")
    )
    module._storage.fetch.assert_not_awaited()
    module.load_module.assert_not_awaited()


def test_restart_loads_approved_copy_without_network(tmp_path):
    module = configured_loader(tmp_path)
    url = "https://example.invalid/test.py"
    doc = "class TestMod(Module): pass"
    module._write_module_cache(url, doc)
    module.load_module = AsyncMock(return_value=True)
    assert asyncio.run(module._load_cached_module(url, "TestMod"))
    assert module.load_module.await_args.args[0] == doc
    module._storage.fetch.assert_not_awaited()


def test_old_always_update_grant_does_not_execute_code(tmp_path):
    module = configured_loader(tmp_path)
    url = "https://example.invalid/test.py"
    old = "class TestMod(Module): pass"
    new = "class TestMod(Module):\n    version = 2"
    module._write_module_cache(url, old)
    module.set("always_update_modules", [url])
    module._storage.fetch.return_value = new
    module.load_module = AsyncMock()
    module._offer_module_update = AsyncMock()
    assert not asyncio.run(module._check_module_update(url))
    module.load_module.assert_not_awaited()
    module._offer_module_update.assert_awaited_once_with(url, new)
    assert Path(module._module_cache_path(url)).read_text() == old


def test_remote_core_update_cannot_replace_approved_cache(tmp_path):
    module = configured_loader(tmp_path)
    url = "https://example.invalid/heroku/modules/loader.py"
    old = "class LoaderMod(Module): pass"
    module._write_module_cache(url, old)
    module._storage.fetch.return_value = old + "\nchanged = True"
    module.load_module = AsyncMock()
    module._offer_module_update = AsyncMock()
    assert not asyncio.run(module._check_module_update(url))
    module.load_module.assert_not_awaited()
    module._offer_module_update.assert_not_awaited()
    assert Path(module._module_cache_path(url)).read_text() == old


def test_missing_modules_remain_in_inventory(tmp_path):
    module = configured_loader(tmp_path)
    expected = {"MissingMod": "https://example.invalid/missing.py"}
    module.set("loaded_modules", expected)
    module.update_modules_in_db()
    assert module.get("loaded_modules") == expected


def test_accept_update_uses_exact_offered_code_and_no_permanent_grant(tmp_path):
    module = configured_loader(tmp_path)
    url = "https://example.invalid/test.py"
    doc = "class TestMod(Module): pass"
    module._pending_module_updates["token"] = (url, doc)
    module.load_module = AsyncMock(return_value=True)
    call = types.SimpleNamespace(edit=AsyncMock())
    module.strings = {"module_update_installed": "installed"}
    asyncio.run(module._accept_module_update(call, "token", always=True))
    assert module.load_module.await_args.args[0] == doc
    assert Path(module._module_cache_path(url)).read_text() == doc
    assert module.get("always_update_modules", []) == []


def test_library_is_pinned_between_process_starts(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "BASE_DIR", str(tmp_path))
    code = "from heroku.types import Library\nclass ExampleLib(Library): pass\n"
    calls = []

    def fetch(url):
        calls.append(url)
        return code

    monkeypatch.setattr("heroku.types.fetch_text", fetch)
    module = Module()
    module.allmodules = types.SimpleNamespace(
        db=MemoryDB(),
        client=types.SimpleNamespace(tg_id=123),
        libraries=[],
        lookup=lambda *args: None,
        get_prefix=lambda: ".",
        get_prefixes=lambda: ["."],
        inline=None,
        allclients=[],
    )
    module.internal_init()
    module.translator = None
    url = "https://example.invalid/library.py"
    asyncio.run(module.import_lib(url))
    # Simulate the next start (no registered library instance).
    module.allmodules.libraries.clear()
    monkeypatch.setattr(
        "heroku.types.fetch_text", lambda url: pytest.fail("unexpected download")
    )
    asyncio.run(module.import_lib(url))
    assert calls == [url]
    assert list((tmp_path / ".libraries_cache" / "123").glob("*.py"))


def test_allow_list_compatibility_does_not_contact_telegram():
    from heroku import version
    from heroku.utils.other import allowed_ids

    client = types.SimpleNamespace(get_messages=AsyncMock(side_effect=AssertionError))
    assert asyncio.run(allowed_ids(client)) is None
    asyncio.run(version.check_branch(123, [456], client))
    client.get_messages.assert_not_awaited()


def test_announcements_stay_disabled():
    loop = UpdaterMod.__dict__["poller_announcement"]
    assert not loop.autostart


def test_update_notice_contains_fork_link_and_works_without_remote_image():
    module = UpdaterMod()
    module.db = module._db = MemoryDB()
    module.tg_id = 123
    module.allclients = []
    module.strings = {"update_required": "Update {} -> {}\n{}"}
    module._markup = lambda: None
    module._get_update_state = lambda: ("a" * 40, "b" * 40, "HerokuSafe 2.2.0")
    send = AsyncMock(return_value=types.SimpleNamespace(message_id=42))
    module.inline = types.SimpleNamespace(bot=types.SimpleNamespace(send_message=send))
    loop = UpdaterMod.__dict__["poller"]
    # InfiniteLoop wraps the decorated coroutine; call it without starting a loop.
    asyncio.run(loop.func(module))
    text = send.await_args.args[1]
    assert REPOSITORY_URL + "/compare/" in text
    assert "Heroku-userbot" not in text
    assert "HerokuSafe 2.2.0" in text
    assert module.get("upd_msg") == 42


def test_updater_defaults_to_manual_installation():
    module = UpdaterMod()
    assert not module.config["autoupdate"]
    assert not module.config["disable_notifications"]
    assert module.config["GIT_ORIGIN_URL"] == REPOSITORY_URL


def test_declined_module_version_does_not_repeat_prompt(tmp_path):
    module = configured_loader(tmp_path)
    url = "https://example.invalid/test.py"
    new = "class TestMod(Module):\n    version = 2"
    module._write_module_cache(url, "class TestMod(Module): pass")
    module._pending_module_updates["token"] = (url, new)
    module.strings = {"module_update_declined": "declined"}
    call = types.SimpleNamespace(edit=AsyncMock())
    asyncio.run(module._decline_module_update(call, "token"))
    module._storage.fetch.return_value = new
    module._offer_module_update = AsyncMock()
    assert not asyncio.run(module._check_module_update(url))
    module._offer_module_update.assert_not_awaited()


def test_dirty_checkout_is_not_overwritten(tmp_path, monkeypatch):
    with git.Repo.init(tmp_path) as repo:
        path = tmp_path / "file"
        path.write_text("base")
        repo.index.add(["file"])
        actor = git.Actor("Test", "test@example.invalid")
        repo.index.commit("base", author=actor, committer=actor)
        repo.git.branch("-M", "master")
        repo.create_remote("origin", REPOSITORY_URL)
        path.write_text("user changes")
        monkeypatch.setattr(
            "heroku.modules.updater.utils.get_base_dir",
            lambda: str(tmp_path / "heroku"),
        )
        with pytest.raises(RuntimeError, match="Local changes"):
            asyncio.run(UpdaterMod().download_common())
        assert path.read_text() == "user changes"


def test_no_git_keeps_restart_available(monkeypatch):
    monkeypatch.setattr("heroku.modules.updater.NO_GIT", True)
    module = UpdaterMod()
    module.db = module._db = MemoryDB()
    module.set("do_not_create", True)
    asyncio.run(module.client_ready())
    assert not module._updates_available
    assert callable(module.restart)
    asyncio.run(module.inline_ready())


def test_nested_pointer_mutations_persist():
    from heroku.pointers import NestedPointerDict

    saved = []
    raw = {"nested": {"items": []}}
    pointer = NestedPointerDict(raw, lambda: saved.append(True))
    pointer["nested"]["items"].append("value")
    assert raw == {"nested": {"items": ["value"]}}
    assert saved


def test_secure_boot_does_not_check_external_module_updates(tmp_path):
    module = configured_loader(tmp_path)
    module.fully_loaded = True
    module._secure_boot = True
    module.set("loaded_modules", {"TestMod": "https://example.invalid/test.py"})
    module._check_module_update = AsyncMock()
    asyncio.run(LoaderMod.__dict__["_auto_update_modules"].func(module))
    module._check_module_update.assert_not_awaited()


def test_forbidden_methods_apply_on_ready(monkeypatch):
    def close_task(coro):
        coro.close()

    monkeypatch.setattr(asyncio, "ensure_future", close_task)
    module = APIRatelimiterMod()
    calls = []
    module._client = types.SimpleNamespace(forbid_constructors=calls.append)
    asyncio.run(module.client_ready())
    assert CONSTRUCTORS["joinChannel"] in calls[0]
    assert CONSTRUCTORS["importChatInvite"] in calls[0]


def test_private_write_and_redaction(tmp_path):
    path = tmp_path / "private.json"
    _internal.private_write(path, "one")
    _internal.private_write(path, "two")
    assert path.read_text() == "two"
    assert list(tmp_path.iterdir()) == [path]
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
    secret = "example-secret-not-a-real-credential"
    _internal.register_secret(secret)
    assert secret not in _internal.redact("token=" + secret)


@pytest.mark.parametrize(
    "url", ["http://example.invalid/mod.py", "https://user:pass@example.invalid/mod.py"]
)
def test_code_downloads_require_https_without_credentials(url):
    with pytest.raises(ValueError):
        _internal.validate_url(url)


def test_basic_auth_does_not_leave_trusted_repository():
    root = "https://example.invalid/private"
    assert _internal.auth_for_url(root + "/mod.py", "user:pass", root) == (
        "user",
        "pass",
    )
    assert (
        _internal.auth_for_url("https://other.invalid/mod.py", "user:pass", root)
        is None
    )
    assert (
        _internal.auth_for_url(
            "https://example.invalid/other/mod.py", "user:pass", root
        )
        is None
    )


def test_all_core_modules_import_without_starting_application():
    for path in (ROOT / "heroku" / "modules").glob("*.py"):
        importlib.import_module("heroku.modules." + path.stem)


def test_all_python_sources_parse():
    for path in (ROOT / "heroku").rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def test_docker_and_installer_do_not_fetch_upstream_code():
    docker = (ROOT / "Dockerfile").read_text()
    assert "COPY . ." in docker
    assert "git clone" not in docker
    assert '"--no-git"' in docker
    assert "qhozek/quiet-lumen-lekq" in (ROOT / "install.sh").read_text()
    assert not (ROOT / "heroku/modules/presets.py").exists()
