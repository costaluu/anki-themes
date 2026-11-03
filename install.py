#!/usr/bin/env python3
"""Install the Themes Anki add-on from this repo on Linux.

Works with the Flatpak Anki (net.ankiweb.Anki) and with a native/other Anki
that keeps its data in ~/.local/share/Anki2. Standard library only.

Examples:
  ./install.py                       # auto-detect targets, install everything
  ./install.py --list                # show detected targets and add-ons
  ./install.py --dry-run             # show what would happen
  ./install.py --target flatpak      # force a target
  ./install.py --link                # symlink instead of copy (for development)
  ./install.py --uninstall           # remove (moved to a backup, not deleted)

Safety rules baked in:
  * An existing add-on folder is MOVED to a backup folder outside addons21
    (Anki treats every folder inside addons21 as an add-on, so backups there
    cause "add-ons failed to start" warnings).
  * The existing meta.json (add-on config) and Contanki's user_files are kept.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
SRC = REPO / "addon"
HOME = Path.home()
XDG_DATA = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
FLATPAK_ID = "net.ankiweb.Anki"
BACKUP_ROOT = XDG_DATA / "anki-addons-backups"

# repo folder name -> (folder name inside addons21, keep-these-user-paths)
ADDONS = {
    "anki-themes": ("anki_themes", []),
}
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.orig", "meta.json")

TARGETS = {
    "flatpak": HOME / ".var/app" / FLATPAK_ID / "data/Anki2/addons21",
    "native": XDG_DATA / "Anki2/addons21",
}


def say(msg: str) -> None:
    print(msg, flush=True)


def anki_running() -> bool:
    for pid in Path("/proc").iterdir():
        if not pid.name.isdigit():
            continue
        try:
            cmd = (pid / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="ignore")
        except OSError:
            continue
        if "aqt" in cmd and "python" in cmd or "/app/bin/anki" in cmd:
            return True
    return False


def flatpak_installed() -> bool:
    if not shutil.which("flatpak"):
        return False
    r = subprocess.run(["flatpak", "info", "--user", FLATPAK_ID],
                       capture_output=True, text=True)
    return r.returncode == 0


def detect_targets(choice: str) -> dict[str, Path]:
    if choice != "auto":
        return {choice: TARGETS[choice]}
    found = {}
    if flatpak_installed() or TARGETS["flatpak"].parent.exists():
        found["flatpak"] = TARGETS["flatpak"]
    if TARGETS["native"].exists():
        found["native"] = TARGETS["native"]
    return found


def backup_dir(stamp: str, label: str) -> Path:
    d = BACKUP_ROOT / stamp / label
    d.mkdir(parents=True, exist_ok=True)
    return d


def install_one(repo_name: str, dest_root: Path, label: str, args, stamp: str) -> None:
    folder, keep = ADDONS[repo_name]
    src = SRC
    dest = dest_root / folder
    old_meta = dest / "meta.json"
    meta_data = None
    if old_meta.exists():
        try:
            meta_data = json.loads(old_meta.read_text())
        except (OSError, ValueError):
            meta_data = None
    say(f"  [{label}] {repo_name} -> {dest}")
    if args.dry_run:
        return

    backup = None
    if dest.exists() or dest.is_symlink():
        backup = backup_dir(stamp, label) / folder
        shutil.move(str(dest), str(backup))
        say(f"      previous version moved to {backup}")

    dest_root.mkdir(parents=True, exist_ok=True)
    if args.link:
        dest.symlink_to(src, target_is_directory=True)
    else:
        shutil.copytree(src, dest, ignore=IGNORE)

    # keep user data that lives inside the add-on folder
    if backup and not args.link:
        for rel in keep:
            old = backup / rel
            if old.is_dir():
                shutil.copytree(old, dest / rel, dirs_exist_ok=True)
    # keep config / settings written by Anki
    if meta_data is not None and not args.link:
        new_meta = dict(meta_data)
        if args.enable:
            new_meta.pop("disabled", None)
        write_meta(dest, new_meta, repo_name)


def write_meta(dest: Path, data: dict, repo_name: str) -> None:
    (dest / "meta.json").write_text(json.dumps(data, ensure_ascii=False))


def uninstall_one(repo_name: str, dest_root: Path, label: str, args, stamp: str) -> None:
    dest = dest_root / ADDONS[repo_name][0]
    if not (dest.exists() or dest.is_symlink()):
        return
    say(f"  [{label}] remove {dest}")
    if args.dry_run:
        return
    backup = backup_dir(stamp, label) / dest.name
    shutil.move(str(dest), str(backup))
    say(f"      moved to {backup}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", choices=["auto", "flatpak", "native"], default="auto")
    p.add_argument("--dest", type=Path, help="explicit addons21 folder (overrides --target)")
    p.add_argument("--link", action="store_true", help="symlink instead of copy")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--list", action="store_true")
    p.add_argument("--uninstall", action="store_true")
    p.add_argument("--enable", action="store_true",
                   help="clear a previous 'disabled' flag in meta.json")
    args = p.parse_args()

    names = list(ADDONS)
    targets = {"custom": args.dest} if args.dest else detect_targets(args.target)

    if args.list:
        say("Add-on in this repo: " + ", ".join(f"{n} -> {ADDONS[n][0]}" for n in ADDONS))
        for k, v in TARGETS.items():
            say(f"Target {k}: {v} ({'found' if v.exists() else 'missing'})")
        say("Flatpak Anki installed: " + str(flatpak_installed()))
        return 0

    if not targets:
        say("No Anki data folder found. Start Anki once, or pass --dest PATH.")
        return 1
    if anki_running() and not args.dry_run:
        say("WARNING: Anki seems to be running. Close it first, or restart it afterwards.")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    for label, root in targets.items():
        for n in names:
            (uninstall_one if args.uninstall else install_one)(n, root, label, args, stamp)

    say("Done." + (" (dry run, nothing changed)" if args.dry_run else
                   " Restart Anki to load the add-ons."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
