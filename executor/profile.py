"""Browser profile management CLI."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.runner import list_profiles, resolve_profile_dir, active_profile_name, _profile_base_dir


def cmd_list(args: argparse.Namespace) -> None:
    profiles = list_profiles()
    if not profiles:
        print("No profiles found.")
        return
    print(f"{'NAME':<30} {'ACTIVE':<8} PATH")
    print("─" * 70)
    for p in profiles:
        marker = "  ●" if p["active"] else ""
        print(f"{p['name']:<30} {marker:<8} {p['path']}")


def cmd_create(args: argparse.Namespace) -> None:
    path = Path(resolve_profile_dir(args.name))
    if path.exists():
        print(f"Profile '{args.name}' already exists at {path}")
        return
    path.mkdir(parents=True)
    print(f"Created profile '{args.name}' at {path}")


def cmd_delete(args: argparse.Namespace) -> None:
    path = Path(resolve_profile_dir(args.name))
    if not path.exists():
        print(f"Profile '{args.name}' does not exist.")
        return
    if active_profile_name() == args.name:
        print(f"Cannot delete active profile '{args.name}'. Switch first.")
        return
    shutil.rmtree(path)
    print(f"Deleted profile '{args.name}'")


def cmd_active(args: argparse.Namespace) -> None:
    name = active_profile_name()
    path = resolve_profile_dir()
    print(f"{name}  ({path})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage browser profiles")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List all profiles")
    sub.add_parser("active", help="Show active profile")

    p_create = sub.add_parser("create", help="Create a named profile")
    p_create.add_argument("name", help="Profile name")

    p_delete = sub.add_parser("delete", help="Delete a named profile")
    p_delete.add_argument("name", help="Profile name")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "create":
        cmd_create(args)
    elif args.command == "delete":
        cmd_delete(args)
    elif args.command == "active":
        cmd_active(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
