"""Entry point for ``python -m luna``.

Usage::

    python -m luna start                    # daemon only (no chat)
    python -m luna start --api              # daemon + API server
    python -m luna chat                     # interactive chat
    python -m luna chat --config luna.toml   # explicit config
    python -m luna chat --log-level DEBUG    # verbose
    python -m luna set-kill-password         # configure kill switch password
    python -m luna kill                      # emergency stop
    python -m luna restore --latest          # restore from most recent backup
    python -m luna restore --list            # list available backups
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from luna.core.config import LunaConfig


# Loggers kept at INFO (visible in console):
#   luna.consciousness.initiative    — Luna's autonomous initiative triggers
#   luna.consciousness.endogenous    — Endogenous impulses (curiosity, affect)
#   luna.chat.session                — Endogenous impulse display + LLM responses
#   luna.consciousness.decider       — Intent decisions
# Everything else → WARNING (file log still captures all at INFO).
_QUIET_LOGGERS: tuple[str, ...] = (
    "luna.orchestrator.cognitive_loop",
    "luna.consciousness.observation_factory",
    "luna.consciousness.thinker",           # obs counts per cycle
    "luna.llm_bridge",
    "luna.memory",
    "luna.dream",
    "luna.api",
    "luna.heartbeat",
    "luna.safety",
    "luna.identity",
    "httpx",
    "httpcore",
    "uvicorn",
)


def _quiet_noisy_loggers() -> None:
    """Set noisy loggers to WARNING on console, keeping file logs untouched."""
    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m luna", description="Luna CLI")
    sub = parser.add_subparsers(dest="command")

    start_parser = sub.add_parser("start", help="Start Luna daemon (no chat)")
    start_parser.add_argument("--config", default="luna.toml", help="Path to luna.toml")
    start_parser.add_argument("--api", action="store_true", help="Also start the API server")
    start_parser.add_argument("--log-level", default="INFO", help="Logging level")

    chat_parser = sub.add_parser("chat", help="Start interactive chat with Luna")
    chat_parser.add_argument("--config", default="luna.toml", help="Path to luna.toml")
    chat_parser.add_argument("--log-level", default="INFO", help="Logging level")

    kill_parser = sub.add_parser("kill", help="Activate kill switch (emergency stop)")
    kill_parser.add_argument("--config", default="luna.toml", help="Path to luna.toml")
    kill_parser.add_argument("--reason", default="manual CLI", help="Reason for kill")
    kill_parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation")

    set_pw_parser = sub.add_parser("set-kill-password", help="Set kill switch password")
    set_pw_parser.add_argument("--config", default="luna.toml", help="Path to luna.toml")

    restore_parser = sub.add_parser("restore", help="Restore state from backup")
    restore_parser.add_argument("--config", default="luna.toml", help="Path to luna.toml")
    restore_parser.add_argument("--latest", action="store_true", help="Restore from most recent backup")
    restore_parser.add_argument("--list", action="store_true", help="List available backups")
    restore_parser.add_argument("--archive", default=None, help="Path to specific archive to restore")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "start":
        log_level = getattr(logging, args.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )
        if log_level > logging.DEBUG:
            _quiet_noisy_loggers()
        config = LunaConfig.load(args.config)

        from luna.orchestrator.cognitive_loop import CognitiveLoop

        if args.api:
            import uvicorn
            from luna.api.app import create_app

            async def run_with_api() -> None:
                from luna.chat.repl import _write_pid, _pid_path
                loop = CognitiveLoop(config)
                await loop.start()
                _write_pid(config)
                app = create_app(loop)
                server_config = uvicorn.Config(
                    app, host=config.api.host, port=config.api.port,
                    log_level="info",
                )
                server = uvicorn.Server(server_config)
                try:
                    await server.serve()
                finally:
                    await loop.stop()
                    _pid_path(config).unlink(missing_ok=True)

            asyncio.run(run_with_api())
        else:
            async def run_daemon() -> None:
                from luna.chat.repl import _write_pid
                loop = CognitiveLoop(config)
                await loop.start()
                _write_pid(config)
                print(
                    f"Luna CognitiveLoop running (tick ~18.5s). "
                    f"Ctrl+C to stop."
                )
                try:
                    while loop.is_running:
                        await asyncio.sleep(1)
                except (KeyboardInterrupt, asyncio.CancelledError):
                    pass
                finally:
                    await loop.stop()
                    from luna.chat.repl import _pid_path
                    _pid_path(config).unlink(missing_ok=True)
                    print("Luna stopped.")

            try:
                asyncio.run(run_daemon())
            except KeyboardInterrupt:
                pass

    elif args.command == "chat":
        log_level = getattr(logging, args.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )
        if log_level > logging.DEBUG:
            _quiet_noisy_loggers()

        config = LunaConfig.load(args.config)

        from luna.chat.repl import run_repl

        try:
            asyncio.run(run_repl(config))
        except KeyboardInterrupt:
            pass  # Already handled inside run_repl.

    elif args.command == "set-kill-password":
        import getpass
        from pathlib import Path

        from luna.safety.kill_auth import (
            DEFAULT_HASH_FILE,
            MIN_PASSWORD_LENGTH,
            hash_password,
            load_hash,
            save_hash,
            verify_password,
        )

        try:
            cfg = LunaConfig.load(args.config)
            root_dir = cfg.root_dir
        except FileNotFoundError:
            root_dir = Path.cwd()

        hash_file = root_dir / DEFAULT_HASH_FILE

        existing = load_hash(hash_file)
        if existing is not None:
            old = getpass.getpass("Current kill switch password: ")
            if not verify_password(old, existing):
                print("ACCESS DENIED: wrong current password.", file=sys.stderr)
                sys.exit(1)

        new_pw = getpass.getpass("New kill switch password (min 12 chars): ")
        if len(new_pw) < MIN_PASSWORD_LENGTH:
            print(f"Password too short — minimum {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
            sys.exit(1)

        confirm = getpass.getpass("Confirm new password: ")
        if new_pw != confirm:
            print("Passwords do not match.", file=sys.stderr)
            sys.exit(1)

        save_hash(hash_file, hash_password(new_pw))
        print(f"Kill switch password saved to {hash_file} (chmod 600)")

    elif args.command == "kill":
        import getpass
        from pathlib import Path

        from luna.safety.kill_auth import DEFAULT_HASH_FILE, require_kill_password
        from luna.safety.kill_switch import KillSwitch

        try:
            cfg = LunaConfig.load(args.config)
            root_dir = cfg.root_dir
            data_dir = cfg.resolve(cfg.luna.data_dir)
        except FileNotFoundError:
            root_dir = Path.cwd()
            data_dir = Path.cwd() / "data"

        hash_file = root_dir / DEFAULT_HASH_FILE
        password = getpass.getpass("Kill switch password: ")
        try:
            require_kill_password(password, hash_file)
        except PermissionError as exc:
            print(f"ACCESS DENIED: {exc}", file=sys.stderr)
            sys.exit(1)

        if not args.force:
            ans = input("Activate kill switch? [y/N] ")
            if ans.lower() not in ("y", "yes"):
                print("Cancelled.")
                sys.exit(0)

        ks = KillSwitch()
        sentinel_path = ks.write_sentinel(data_dir, args.reason)
        print(f"Emergency stop written: {sentinel_path}")
        print(f"Reason: {args.reason}")
        print("Luna will detect this on next message (chat) or heartbeat cycle.")

    elif args.command == "restore":
        from pathlib import Path

        from luna.safety.state_backup import StateBackup

        try:
            cfg = LunaConfig.load(args.config)
        except FileNotFoundError:
            print(f"Config not found: {args.config}", file=sys.stderr)
            sys.exit(1)

        memory_root = cfg.resolve(cfg.memory.fractal_root)
        backup_dir = cfg.resolve(cfg.backup.backup_dir)
        sb = StateBackup(
            memory_root=memory_root,
            backup_dir=backup_dir,
            max_backups=cfg.backup.max_backups,
        )

        if args.list:
            backups = sb.list_backups()
            if not backups:
                print("No backups available.")
            else:
                print(f"Available backups ({len(backups)}):\n")
                for i, b in enumerate(backups):
                    size_kb = b.stat().st_size / 1024
                    print(f"  [{i}] {b.name}  ({size_kb:.1f} KB)")
                status = sb.get_status()
                print(f"\n  Compression: {status['compression']}")
                print(f"  Archive dir: {status['archive_count']} archived")

        elif args.latest:
            ans = input(
                f"Restore latest backup to {memory_root}?\n"
                f"This will OVERWRITE existing files. [y/N] "
            )
            if ans.lower() not in ("y", "yes"):
                print("Cancelled.")
                sys.exit(0)

            if sb.restore_latest():
                print("Restore complete.")
            else:
                print("Restore failed — check logs.", file=sys.stderr)
                sys.exit(1)

        elif args.archive:
            archive_path = Path(args.archive)
            if not archive_path.exists():
                print(f"Archive not found: {archive_path}", file=sys.stderr)
                sys.exit(1)

            ans = input(
                f"Restore from {archive_path.name} to {memory_root}?\n"
                f"This will OVERWRITE existing files. [y/N] "
            )
            if ans.lower() not in ("y", "yes"):
                print("Cancelled.")
                sys.exit(0)

            if sb.restore_from(archive_path):
                print("Restore complete.")
            else:
                print("Restore failed — check logs.", file=sys.stderr)
                sys.exit(1)

        else:
            print("Usage: python -m luna restore --latest | --list | --archive <path>")
            sys.exit(1)


if __name__ == "__main__":
    main()
