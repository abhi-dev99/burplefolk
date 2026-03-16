import argparse
import time

import pandas as pd

import app


def build_csv_bundle(rows_per_table: int) -> dict:
    customers = pd.DataFrame(
        {
            "customer_id": range(1, rows_per_table + 1),
            "customer_name": [f"cust_{i}" for i in range(1, rows_per_table + 1)],
            "country": ["IN"] * rows_per_table,
            "created_at": ["2026-03-01"] * rows_per_table,
        }
    )
    orders = pd.DataFrame(
        {
            "order_id": range(1, rows_per_table + 1),
            "customer_id": range(1, rows_per_table + 1),
            "amount": [float((i % 1000) + 1) for i in range(1, rows_per_table + 1)],
            "status": ["completed" if i % 10 else "refund" for i in range(1, rows_per_table + 1)],
            "created_at": ["2026-03-02"] * rows_per_table,
        }
    )
    payments = pd.DataFrame(
        {
            "payment_id": range(1, rows_per_table + 1),
            "order_id": range(1, rows_per_table + 1),
            "payment_status": ["paid" if i % 15 else "failed" for i in range(1, rows_per_table + 1)],
            "paid_at": ["2026-03-03"] * rows_per_table,
        }
    )

    return {
        "customers.csv": customers.to_csv(index=False).encode(),
        "orders.csv": orders.to_csv(index=False).encode(),
        "payments.csv": payments.to_csv(index=False).encode(),
    }


def run_once(rows_per_table: int, profile_row_limit: int) -> None:
    t0 = time.perf_counter()
    files = build_csv_bundle(rows_per_table)
    t1 = time.perf_counter()
    result = app.run_analysis("CSV Bundle", files, profile_row_limit)
    t2 = time.perf_counter()

    print("=== Benchmark Result ===")
    print(f"rows_per_table: {rows_per_table}")
    print(f"profile_row_limit: {profile_row_limit}")
    print(f"tables_detected: {len(result['table_profiles'])}")
    print(f"relationships_detected: {len(result['relationships'])}")
    print(f"avg_quality_score: {result['avg_quality_score']}")
    print(f"data_generation_sec: {round(t1 - t0, 2)}")
    print(f"analysis_sec: {round(t2 - t1, 2)}")
    print(f"total_sec: {round(t2 - t0, 2)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark scaling limits for Nexus DB intelligence pipeline.")
    parser.add_argument("--rows", type=int, default=250000, help="Rows per table for synthetic dataset.")
    parser.add_argument("--limit", type=int, default=25000, help="profile_row_limit passed to run_analysis.")
    args = parser.parse_args()

    run_once(args.rows, args.limit)


if __name__ == "__main__":
    main()
