"""Small argparse entry point; only implemented milestones are exposed."""

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from .records import canonical_json


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="depverify")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Check the fake-only M0 environment")
    doctor.add_argument("--fake", required=True, action="store_true")
    from .pipeline import REPO_ROOT
    doctor.add_argument("--config", type=Path, default=REPO_ROOT / "config.toml")
    doctor.add_argument("--run-dir", type=Path, default=Path("runs/m0"))
    simulate = commands.add_parser("simulate", help="Run deterministic mathematical/protocol controls")
    simulate.add_argument("--suite", choices=("core",), required=True)
    simulate.add_argument("--run-dir", type=Path, default=Path("runs/m0"))
    report = commands.add_parser("report", help="Report the executed evidence prefix")
    report.add_argument("--run-dir", type=Path, default=Path("runs/m0"))
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            from .pipeline import doctor_fake
            result = doctor_fake(args.run_dir, args.config)
        elif args.command == "simulate":
            from .evaluate import run_core_suite
            result = run_core_suite(args.run_dir)
        else:
            from .evaluate import render_report
            print(render_report(args.run_dir), end="")
            return 0
        print(canonical_json(result).decode("utf-8"))
        return 0 if result.get("passed", True) else 1
    except (OSError, ValueError) as exc:
        print(f"depverify: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
