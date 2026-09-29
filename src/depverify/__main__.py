"""Small argparse entry point; only implemented milestones are exposed."""

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from .records import canonical_json


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="depverify")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Check the fake or local execution prerequisites")
    mode = doctor.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fake", action="store_true")
    mode.add_argument("--local", action="store_true")
    from .pipeline import REPO_ROOT
    doctor.add_argument("--config", type=Path, default=REPO_ROOT / "config.toml")
    doctor.add_argument("--run-dir", type=Path)
    simulate = commands.add_parser("simulate", help="Run deterministic mathematical/protocol controls")
    simulate.add_argument("--suite", choices=("core",), required=True)
    simulate.add_argument("--run-dir", type=Path, default=Path("runs/m0"))
    smoke = commands.add_parser("smoke", help="Run only the gated M1 native-model smoke test")
    smoke.add_argument("--config", type=Path, default=REPO_ROOT / "config.toml")
    smoke.add_argument("--run-dir", type=Path, default=Path("runs/m1"))
    report = commands.add_parser("report", help="Report the executed evidence prefix")
    report.add_argument("--run-dir", type=Path, default=Path("runs/m0"))
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            if args.fake:
                from .pipeline import doctor_fake
                result = doctor_fake(args.run_dir or Path("runs/m0"), args.config)
            else:
                from .resources import doctor_local
                result = doctor_local(args.run_dir or Path("runs/m1"), args.config)
        elif args.command == "simulate":
            from .evaluate import run_core_suite
            result = run_core_suite(args.run_dir)
        elif args.command == "smoke":
            from .smoke import smoke_local
            result = smoke_local(args.run_dir, args.config)
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
