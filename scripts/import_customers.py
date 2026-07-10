"""Import a QuickBooks Customer Contact List export into a brand's customer tables (§13).

Preview by default (no writes); pass --apply to insert the new (non-duplicate) rows.
Dedupe is on phone/email, so re-running the same export inserts nothing.

    python -m scripts.import_customers path/to/customers.csv            # preview only
    python -m scripts.import_customers path/to/customers.csv --apply    # write new rows
    python -m scripts.import_customers path/to/customers.csv --brand nanaimo --apply
"""
from __future__ import annotations

import argparse
from pathlib import Path

from app.customers.qb_import import apply_import, build_preview, parse_csv
from app.db.session import new_session
from app.models.enums import Brand


def main() -> None:
    ap = argparse.ArgumentParser(description="Import a QuickBooks Customer Contact List export.")
    ap.add_argument("file", help="path to the QuickBooks CSV export")
    ap.add_argument("--brand", default="victoria", choices=[b.value for b in Brand])
    ap.add_argument("--apply", action="store_true", help="write new rows (default: preview only)")
    args = ap.parse_args()

    text = Path(args.file).read_text(encoding="utf-8-sig")
    rows = parse_csv(text)
    brand = Brand(args.brand)
    print(f"Parsed {len(rows)} data rows from {args.file} (brand={brand.value}).")

    db = new_session()
    try:
        prev = build_preview(db, brand, rows)
        c = prev["counts"]
        print(f"  residential: {c['residential_new']} new, {c['residential_dup']} duplicate")
        print(f"  company:     {c['company_new']} new, {c['company_dup']} duplicate")
        print(f"  unusable rows (no name/phone/email): {c['skipped']}")
        if args.apply:
            res = apply_import(db, brand, rows)
            print(f"APPLIED -> +{res['added_residential']} residential, +{res['added_company']} company "
                  f"(skipped {res['skipped_duplicates']} duplicates).")
        else:
            print("Preview only. Re-run with --apply to write the new rows.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
