"""Check PyPI twice-daily automation for updating and pushing yt-dlp."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"
PACKAGE = "yt-dlp"
PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"
COMMIT_PREFIX = "chore(deps): update yt-dlp to "
TASK_TIMES = ("08:00", "20:00")
PIN_PATTERN = re.compile(
    r"^(?P<prefix>\s*yt-dlp(?:\[[^\]]+\])?==)"
    r"(?P<version>[0-9]+(?:\.[0-9]+)*)"
    r"(?P<suffix>\s*(?:\#.*)?(?:\r?\n)?)$",
    re.IGNORECASE,
)


def _configure_logging() -> None:
    log_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "UVD-backend" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "yt-dlp-updater.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def _version_key(version: str) -> tuple[int, ...]:
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", version):
        raise ValueError(f"Unsupported yt-dlp version format: {version}")
    parts = [int(part) for part in version.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def _requirements_pin(contents: str) -> tuple[str, str, str, str]:
    matches = [
        match
        for line in contents.splitlines(keepends=True)
        if (match := PIN_PATTERN.fullmatch(line))
    ]
    if len(matches) != 1:
        raise ValueError("requirements.txt must contain exactly one pinned yt-dlp requirement")
    match = matches[0]
    return match.group("prefix"), match.group("version"), match.group("suffix"), match.group(0)


def _replace_pin(contents: str, latest_version: str) -> str:
    prefix, _current, suffix, full_line = _requirements_pin(contents)
    replacement = f"{prefix}{latest_version}{suffix}"
    return contents.replace(full_line, replacement, 1)


def _git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Git command failed")
    return result.stdout.strip()


def _fetch_pypi_version() -> str:
    with urlopen(PYPI_URL, timeout=30) as response:
        payload = json.load(response)
    version = payload["info"]["version"]
    _version_key(version)
    return version


def _https_remote_url(remote_url: str) -> str:
    if remote_url.startswith("git@github.com:"):
        return "https://github.com/" + remote_url.removeprefix("git@github.com:")
    if remote_url.startswith("ssh://git@github.com/"):
        return "https://github.com/" + remote_url.removeprefix("ssh://git@github.com/")
    return remote_url


def _upstream_state() -> tuple[str, str, str, list[str]]:
    branch = _git("branch", "--show-current")
    if not branch:
        raise RuntimeError("Detached HEAD is not supported; check out the branch you want updated")

    upstream = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if "/" not in upstream:
        raise RuntimeError(f"Expected an origin/branch upstream, got {upstream}")
    remote, remote_branch = upstream.split("/", 1)
    if remote_branch != branch:
        raise RuntimeError("The upstream branch must have the same name as the checked-out branch")

    remote_url = _https_remote_url(_git("remote", "get-url", remote))
    _git(
        "fetch",
        remote_url,
        f"+refs/heads/{remote_branch}:refs/remotes/{remote}/{remote_branch}",
    )
    remote_head = _git("rev-parse", f"refs/remotes/{remote}/{remote_branch}")
    local_head = _git("rev-parse", "HEAD")
    ahead = _git("rev-list", f"{remote_head}..HEAD").splitlines()
    return remote_url, remote_branch, remote_head, ahead


def _is_automation_commit(commit: str) -> bool:
    subject = _git("show", "-s", "--format=%s", commit)
    files = _git("diff-tree", "--no-commit-id", "--name-only", "-r", commit).splitlines()
    return subject.startswith(COMMIT_PREFIX) and files == ["requirements.txt"]


def _push_pending_updates(remote_url: str, branch: str, ahead: list[str]) -> bool:
    if not ahead:
        return False
    if not all(_is_automation_commit(commit) for commit in ahead):
        raise RuntimeError(
            "Local branch has commits that are not yt-dlp updater commits; refusing to push them"
        )
    _git("push", remote_url, f"HEAD:{branch}")
    logging.info("Pushed pending yt-dlp update commit(s) to origin/%s", branch)
    return True


def update(*, check_only: bool = False) -> bool:
    contents = REQUIREMENTS.read_text(encoding="utf-8")
    _prefix, current_version, _suffix, _line = _requirements_pin(contents)
    latest_version = _fetch_pypi_version()
    logging.info("Installed project pin: %s; latest PyPI version: %s", current_version, latest_version)

    if check_only:
        if _version_key(latest_version) > _version_key(current_version):
            logging.info("Update available; check-only mode made no changes")
            return True
        logging.info("yt-dlp is already up to date")
        return False

    remote_url, branch, remote_head, ahead = _upstream_state()
    if _push_pending_updates(remote_url, branch, ahead):
        return True

    if _git("rev-parse", "HEAD") != remote_head:
        raise RuntimeError("Local branch is behind or diverged from its upstream; synchronize it first")

    status = _git("status", "--porcelain", "--", str(REQUIREMENTS.relative_to(ROOT)))
    if status:
        raise RuntimeError("requirements.txt has local changes; refusing to overwrite or commit them")

    if _version_key(latest_version) <= _version_key(current_version):
        logging.info("yt-dlp is already up to date")
        return False

    requirement = f"yt-dlp[default,curl-cffi]=={latest_version}"
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", requirement],
        cwd=ROOT,
        check=True,
    )

    updated_contents = _replace_pin(contents, latest_version)
    REQUIREMENTS.write_text(updated_contents, encoding="utf-8", newline="")
    _git("commit", "--only", "-m", f"{COMMIT_PREFIX}{latest_version}", "--", "requirements.txt")
    _git("push", remote_url, f"HEAD:{branch}")
    logging.info("Updated yt-dlp to %s and pushed to origin/%s", latest_version, branch)
    return True


def install_schedule() -> None:
    script = Path(__file__).resolve()
    task_command = f'"{sys.executable}" "{script}"'
    for time in TASK_TIMES:
        task_name = f"UVD yt-dlp update {time.replace(':', '')}"
        subprocess.run(
            [
                "schtasks.exe",
                "/Create",
                "/SC",
                "DAILY",
                "/ST",
                time,
                "/TN",
                task_name,
                "/TR",
                task_command,
                "/F",
            ],
            cwd=ROOT,
            check=True,
        )
        logging.info("Scheduled %s daily at %s", task_name, time)


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep the pinned yt-dlp dependency updated.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--check",
        action="store_true",
        help="check PyPI without installing, editing files, committing, or pushing",
    )
    modes.add_argument(
        "--install-schedule",
        action="store_true",
        help="schedule daily runs at 08:00 and 20:00 using Windows Task Scheduler",
    )
    args = parser.parse_args()

    _configure_logging()
    try:
        if args.install_schedule:
            install_schedule()
            return 0
        update(check_only=args.check)
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        logging.exception("yt-dlp updater failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
