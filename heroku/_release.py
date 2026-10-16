"""HerokuSafe's update trust root, independent of the original project."""

from urllib.parse import urlsplit

REPOSITORY = "qhozek/quiet-lumen-lekq"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
UPDATE_BRANCH = "master"
UPSTREAM_SNAPSHOT = "19f4a8f82159497d2f67e1fcbea8cab4249b3346"


def is_safe_origin(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.netloc.lower() == "github.com"
            and parsed.path.removesuffix(".git").rstrip("/").lower()
            == f"/{REPOSITORY}".lower()
            and not parsed.query
            and not parsed.fragment
        )
    except (TypeError, ValueError):
        return False
