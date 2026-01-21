"""Process churned accounts from the last N months."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class Account:
    account_id: str
    account_name: str
    churned_at: date
    churn_reason: Optional[str] = None
    owner: Optional[str] = None


@dataclass(frozen=True)
class ReviewItem:
    account: Account
    review_notes: str
    next_action: str


def _subtract_months(anchor: date, months: int) -> date:
    """Return a date that is `months` before the anchor date."""
    total_months = anchor.year * 12 + (anchor.month - 1) - months
    year = total_months // 12
    month = total_months % 12 + 1
    day = min(anchor.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (next_month - date(year, month, 1)).days


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def load_accounts_from_csv(path: Path) -> List[Account]:
    accounts: List[Account] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            churned_at = _parse_date(row["churned_at"])
            accounts.append(
                Account(
                    account_id=row["account_id"],
                    account_name=row["account_name"],
                    churned_at=churned_at,
                    churn_reason=row.get("churn_reason") or None,
                    owner=row.get("owner") or None,
                )
            )
    return accounts


def load_accounts_from_json(path: Path) -> List[Account]:
    data = json.loads(path.read_text(encoding="utf-8"))
    accounts: List[Account] = []
    for entry in data:
        accounts.append(
            Account(
                account_id=entry["account_id"],
                account_name=entry["account_name"],
                churned_at=_parse_date(entry["churned_at"]),
                churn_reason=entry.get("churn_reason"),
                owner=entry.get("owner"),
            )
        )
    return accounts


def select_recent_churns(
    accounts: Iterable[Account],
    *,
    months: int = 3,
    as_of: Optional[date] = None,
) -> List[Account]:
    """Filter accounts that churned within the last `months`."""
    if as_of is None:
        as_of = date.today()
    cutoff = _subtract_months(as_of, months)
    return [
        account
        for account in accounts
        if cutoff <= account.churned_at <= as_of
    ]


def build_review_plan(accounts: Iterable[Account]) -> List[ReviewItem]:
    """Build a review plan for churned accounts."""
    review_items: List[ReviewItem] = []
    for account in accounts:
        notes = "Confirm churn reason and validate offboarding completion."
        action = "Schedule follow-up with account owner."
        if account.churn_reason:
            notes = f"Review churn reason: {account.churn_reason}."
        if account.owner:
            action = f"Schedule follow-up with {account.owner}."
        review_items.append(
            ReviewItem(account=account, review_notes=notes, next_action=action)
        )
    return review_items


def run_review(input_path: Path, *, months: int = 3) -> List[ReviewItem]:
    if input_path.suffix.lower() == ".csv":
        accounts = load_accounts_from_csv(input_path)
    elif input_path.suffix.lower() == ".json":
        accounts = load_accounts_from_json(input_path)
    else:
        raise ValueError("Supported input formats: .csv, .json")

    recent_churns = select_recent_churns(accounts, months=months)
    return build_review_plan(recent_churns)


def _print_review(items: Iterable[ReviewItem]) -> None:
    for item in items:
        account = item.account
        print(
            " | ".join(
                [
                    account.account_id,
                    account.account_name,
                    account.churned_at.isoformat(),
                    item.review_notes,
                    item.next_action,
                ]
            )
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Review accounts that churned in the last N months."
    )
    parser.add_argument("input_path", type=Path, help="Path to a CSV or JSON file")
    parser.add_argument("--months", type=int, default=3, help="Months to look back")

    args = parser.parse_args()
    results = run_review(args.input_path, months=args.months)
    _print_review(results)
