import argparse
import csv
from pathlib import Path

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.services import all_balances, export_balances, import_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="SplitUZ dataset tools")
    sub = parser.add_subparsers(dest="command", required=True)
    importer = sub.add_parser("import")
    importer.add_argument("directory", type=Path, nargs="?", default=settings.dataset_dir)
    exporter = sub.add_parser("export")
    exporter.add_argument("output", type=Path, nargs="?", default=settings.result_dir / "balanslar.csv")
    verifier = sub.add_parser("verify")
    verifier.add_argument("expected", type=Path)
    args = parser.parse_args()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if args.command == "import":
            print(import_dataset(db, args.directory))
        elif args.command == "export":
            print(f"Exported {export_balances(db, args.output)} rows to {args.output}")
        else:
            actual = {(g, m): value for g, balances in all_balances(db).items() for m, value in balances.items()}
            with args.expected.open(encoding="utf-8-sig", newline="") as handle:
                expected = {(r["group_id"], r["member_id"]): int(r["net_balans"]) for r in csv.DictReader(handle)}
            differences = [(key, expected.get(key), actual.get(key)) for key in sorted(set(expected) | set(actual)) if expected.get(key) != actual.get(key)]
            if differences:
                for row in differences[:20]:
                    print(row)
                raise SystemExit(f"FAILED: {len(differences)} differences")
            print(f"OK: all {len(actual)} balances match exactly")


if __name__ == "__main__":
    main()

