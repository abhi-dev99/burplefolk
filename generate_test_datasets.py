import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import sqlite3


def make_base(n: int = 50000):
    customers = pd.DataFrame(
        {
            "customer_id": np.arange(1, n + 1),
            "customer_name": [f"customer_{i}" for i in range(1, n + 1)],
            "country": np.random.choice(["IN", "US", "UK", "DE"], size=n),
            "created_at": pd.date_range("2025-01-01", periods=n, freq="min").astype(str),
        }
    )

    orders = pd.DataFrame(
        {
            "order_id": np.arange(1, n + 1),
            "customer_id": np.arange(1, n + 1),
            "amount": np.random.uniform(10, 10000, size=n).round(2),
            "order_status": np.random.choice(["placed", "shipped", "delivered", "cancelled"], size=n),
            "created_at": pd.date_range("2025-01-03", periods=n, freq="min").astype(str),
        }
    )

    payments = pd.DataFrame(
        {
            "payment_id": np.arange(1, n + 1),
            "order_id": np.arange(1, n + 1),
            "payment_status": np.random.choice(["paid", "failed", "refunded"], size=n),
            "paid_at": pd.date_range("2025-01-05", periods=n, freq="min").astype(str),
        }
    )
    return customers, orders, payments


def write_bundle(path: Path, customers: pd.DataFrame, orders: pd.DataFrame, payments: pd.DataFrame):
    path.mkdir(parents=True, exist_ok=True)
    customers.to_csv(path / "customers.csv", index=False)
    orders.to_csv(path / "orders.csv", index=False)
    payments.to_csv(path / "payments.csv", index=False)


def build_clean(out_root: Path, n: int):
    c, o, p = make_base(n)
    write_bundle(out_root / "clean_bundle", c, o, p)


def build_quality_issues(out_root: Path, n: int):
    c, o, p = make_base(n)

    # Missingness spikes
    c.loc[c.sample(frac=0.25, random_state=42).index, "customer_name"] = None
    o.loc[o.sample(frac=0.30, random_state=11).index, "amount"] = None

    # Duplicate identifier rows
    dup_rows = o.sample(2000, random_state=9).copy()
    o = pd.concat([o, dup_rows], ignore_index=True)

    # Type inconsistency and malformed dates
    o["amount"] = o["amount"].astype(object)
    bad_idx = o.sample(3000, random_state=7).index
    o.loc[bad_idx, "amount"] = "unknown"
    date_idx = p.sample(2500, random_state=5).index
    p.loc[date_idx, "paid_at"] = "not-a-date"

    # Stale timestamps
    stale_idx = c.sample(5000, random_state=3).index
    c.loc[stale_idx, "created_at"] = "2014-01-01 00:00:00"

    write_bundle(out_root / "quality_issues_bundle", c, o, p)


def build_schema_issues(out_root: Path, n: int):
    c, o, p = make_base(n)

    # Orphan references: orders.customer_id not in customers
    orphan_idx = o.sample(4000, random_state=22).index
    o.loc[orphan_idx, "customer_id"] = o.loc[orphan_idx, "customer_id"] + n + 500

    # Mismatched join key naming and semantics
    p = p.rename(columns={"order_id": "order_ref"})

    # Add noisy table with no clear keys
    sessions = pd.DataFrame(
        {
            "session": np.random.choice(["A", "B", "C", "D"], size=n),
            "metric": np.random.randn(n),
            "event_time": pd.date_range("2024-01-01", periods=n, freq="min").astype(str),
        }
    )

    target = out_root / "schema_issues_bundle"
    target.mkdir(parents=True, exist_ok=True)
    c.to_csv(target / "customers.csv", index=False)
    o.to_csv(target / "orders.csv", index=False)
    p.to_csv(target / "payments.csv", index=False)
    sessions.to_csv(target / "sessions.csv", index=False)


def build_sqlite_bundle(out_root: Path, n: int):
    c, o, p = make_base(min(n, 100000))
    db_path = out_root / "sqlite_demo" / "enterprise_demo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        c.to_sql("customers", conn, index=False)
        o.to_sql("orders", conn, index=False)
        p.to_sql("payments", conn, index=False)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Generate clean and intentionally broken datasets for Nexus testing")
    parser.add_argument("--out", default="outputs/test_scenarios", help="Output root folder")
    parser.add_argument("--rows", type=int, default=50000, help="Base rows per table")
    args = parser.parse_args()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    build_clean(out_root, args.rows)
    build_quality_issues(out_root, args.rows)
    build_schema_issues(out_root, args.rows)
    build_sqlite_bundle(out_root, args.rows)

    print("Generated scenarios:")
    print(f"- {out_root / 'clean_bundle'}")
    print(f"- {out_root / 'quality_issues_bundle'}")
    print(f"- {out_root / 'schema_issues_bundle'}")
    print(f"- {out_root / 'sqlite_demo' / 'enterprise_demo.db'}")


if __name__ == "__main__":
    main()
