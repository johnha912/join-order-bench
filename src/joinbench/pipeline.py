"""joinbench CLI: generate -> dbt build -> (load postgres) -> bench -> report.

    joinbench all --sf 1                      # DuckDB only
    joinbench all --sf 1 --postgres           # also Postgres (docker compose up -d)
"""

import argparse
import csv
import json
import os
import subprocess
from pathlib import Path

import duckdb

from . import bench, report
from .chains import CHAINS

ROOT = Path(__file__).resolve().parents[2]
TABLES = ["region", "nation", "customer", "orders", "lineitem", "part", "supplier", "partsupp"]
PG_DSN = os.environ.get(
    "JOINBENCH_PG", "host=localhost port=5432 dbname=postgres user=postgres password=postgres"
)


def tag(sf):
    return f"sf{sf:g}".replace(".", "_")  # dbt names the catalog after the file stem


def paths(sf):
    return ROOT / "data" / "raw" / tag(sf), ROOT / "data" / f"tpch_{tag(sf)}.duckdb"


def generate(sf, out):
    """TPC-H at scale factor sf as one parquet file per table: the raw landing zone."""
    subprocess.run(["tpchgen-cli", "parquet", "-s", f"{sf:g}", f"--output-dir={out}"], check=True)


def dbt_build(sf):
    """Load parquet into the warehouse and run the key/foreign-key tests the
    cost model depends on. A failed test stops the pipeline."""
    raw, db = paths(sf)
    project = str(ROOT / "dbt")
    subprocess.run(  # own process: dbt-duckdb keeps its connection open after an in-process run
        ["dbt", "build", "--project-dir", project, "--profiles-dir", project,
         "--vars", json.dumps({"raw_dir": raw.as_posix()})],
        check=True, env={**os.environ, "JOINBENCH_DB": db.as_posix()},
    )


def load_postgres(sf):
    """Copy the warehouse tables into Postgres (CSV over COPY), add primary keys, analyze."""
    raw, db = paths(sf)
    con = duckdb.connect(str(db), read_only=True)
    pg = bench.Postgres(PG_DSN)
    for t in TABLES:
        cols = ", ".join(f"{name} {type_}" for name, type_, *_ in con.execute(f"DESCRIBE {t}").fetchall())
        pg.scalar(f"DROP TABLE IF EXISTS {t}")
        pg.scalar(f"CREATE TABLE {t} ({cols})")
        tmp = raw / f"{t}.csv"
        con.execute(f"COPY {t} TO '{tmp.as_posix()}' (HEADER)")
        with (pg.con.cursor() as cur, cur.copy(f"COPY {t} FROM STDIN (FORMAT csv, HEADER)") as cp,
              open(tmp, "rb") as f):
            while chunk := f.read(1 << 20):
                cp.write(chunk)
        tmp.unlink()
    con.close()
    for table, key in {(t, k) for c in CHAINS for _, t, k in c.edges}:
        pg.scalar(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_pkey")
        pg.scalar(f"ALTER TABLE {table} ADD PRIMARY KEY ({key})")
    pg.scalar("ANALYZE")


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="joinbench")
    ap.add_argument("step", choices=["generate", "dbt", "bench", "report", "all"])
    ap.add_argument("--sf", type=float, default=1)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--postgres", action="store_true", help="also benchmark Postgres at JOINBENCH_PG")
    args = ap.parse_args(argv)
    plans_csv = ROOT / "results" / f"plans_{tag(args.sf)}.csv"
    card_csv = ROOT / "results" / f"cardinalities_{tag(args.sf)}.csv"

    if args.step in ("generate", "all"):
        print(f"generate TPC-H {tag(args.sf)}")
        generate(args.sf, paths(args.sf)[0])
    if args.step in ("dbt", "all"):
        dbt_build(args.sf)
    if args.step in ("bench", "all"):
        if args.postgres:
            load_postgres(args.sf)  # before the read-only DuckDB connection below opens
        duck = bench.DuckDB(paths(args.sf)[1])
        write_csv(card_csv, bench.cardinalities(duck, args.sf))
        rows = bench.run(duck, args.sf, args.repeats)
        if args.postgres:
            rows += bench.run(bench.Postgres(PG_DSN), args.sf, args.repeats)
        write_csv(plans_csv, rows)
    if args.step in ("report", "all"):
        out = ROOT / "docs" / "index.html"
        report.build(plans_csv, card_csv, out)
        print(f"report -> {out}")


if __name__ == "__main__":
    main()
