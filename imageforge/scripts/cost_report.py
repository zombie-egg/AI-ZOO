from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="ImageForge 成本与毛利粗算")
    parser.add_argument("--db", type=Path, default=Path("data/imageforge.db"))
    parser.add_argument("--sale-cents", type=int, default=1990)
    parser.add_argument("--print-cents", type=int, default=180)
    parser.add_argument("--template-investment-cents", type=int, default=0)
    parser.add_argument("--template-amortized-orders", type=int, default=1000)
    args = parser.parse_args()
    conn = sqlite3.connect(args.db)
    rows = conn.execute("SELECT status, cost_cents FROM finalize_job").fetchall()
    conn.close()
    provider_cost = sum(row[1] for row in rows)
    orders = len(rows)
    template_per_order = args.template_investment_cents / max(args.template_amortized_orders, 1)
    average_provider = provider_cost / max(orders, 1)
    gross_cost = average_provider + args.print_cents + template_per_order
    margin = (args.sale_cents - gross_cost) / args.sale_cents if args.sale_cents else 0
    print(f"orders={orders}")
    print("preview_external_api_cost_cents=0")
    print(f"average_finalize_provider_cost_cents={average_provider:.2f}")
    print(f"estimated_gross_margin={margin:.2%}")
    return 0 if margin >= 0.75 else 1


if __name__ == "__main__":
    raise SystemExit(main())

