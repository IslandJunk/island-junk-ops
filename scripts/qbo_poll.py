"""Render Cron entrypoint — poll QuickBooks (READ-ONLY) for every auto-sync-enabled brand.

    python -m scripts.qbo_poll

Prints one line per brand. Always exits 0 (a per-brand error is logged, not raised) so a single
bad connection never fails the whole cron run. Reads QBO only — never creates/sends an invoice
or charges a card.
"""
from __future__ import annotations

from app.db.session import new_session
from app.quickbooks.poll import poll_all


def main() -> None:
    db = new_session()
    try:
        results = poll_all(db)
        if not results:
            print("qbo-poll: no brands with auto-sync enabled")
        for r in results:
            print("qbo-poll:", r)
    finally:
        db.close()


if __name__ == "__main__":
    main()
