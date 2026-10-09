"""Time every join tree of every chain, forced, on a real engine.

Forcing the order: DuckDB with its join_order optimizer disabled, Postgres with
join_collapse_limit = 1. Both then execute the explicit JOIN nesting as written.
The "engine" row is the same query with the optimizer back on.
"""

import statistics
import time

import duckdb

from .chains import CHAINS, label, left_deep, model_cost, pick, trees
from .cost_model import join_cost, size_table


class DuckDB:
    name = "duckdb"

    def __init__(self, path):
        self.con = duckdb.connect(str(path), read_only=True)

    def scalar(self, sql):
        return self.con.execute(sql).fetchone()[0]

    def force_order(self, on):
        self.con.execute("SET disabled_optimizers = 'join_order'" if on else "RESET disabled_optimizers")


class Postgres:
    name = "postgres"

    def __init__(self, dsn):
        import psycopg

        self.con = psycopg.connect(dsn, autocommit=True)

    def scalar(self, sql):
        with self.con.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()[0] if cur.description else None

    def force_order(self, on):
        self.scalar(f"SET join_collapse_limit = {1 if on else 8}")


def timed(engine, sql, repeats):
    rows = engine.scalar(sql)  # warm-up, also the answer every plan must match
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        engine.scalar(sql)
        times.append(time.perf_counter() - t0)
    return statistics.median(times), rows


def model_inputs(engine, chain):
    """Single-table stats only, as an optimizer would have: filtered row counts,
    and 1/|pk table| per foreign-key edge."""
    sizes = [engine.scalar(chain.sql(i)) for i in range(1, chain.n + 1)]
    sel = [1 / engine.scalar(f"SELECT count(*) FROM {pk_table}") for _, pk_table, _ in chain.edges]
    return sizes, sel


def cardinalities(engine, sf):
    """Estimated vs actual rows for every contiguous span of every chain."""
    out = []
    for chain in CHAINS:
        sizes, sel = model_inputs(engine, chain)
        est = size_table(sizes, sel)
        for i in range(1, chain.n + 1):
            for j in range(i + 1, chain.n + 1):
                out.append({
                    "sf": sf, "chain": chain.name, "span": "-".join(chain.names[i - 1:j]),
                    "estimated": est[i][j], "actual": engine.scalar(chain.sql(left_deep(i, j))),
                })
    return out


def run(engine, sf, repeats, log=print):
    out = []
    for chain in CHAINS:
        sizes, sel = model_inputs(engine, chain)
        cost = join_cost(size_table(sizes, sel), sel)
        chosen = pick(sizes, sel, chain.names)
        answer = None

        engine.force_order(True)
        all_trees = list(trees(1, chain.n))
        for t in all_trees:
            seconds, rows = timed(engine, chain.sql(t), repeats)
            assert answer in (None, rows), f"{chain.name}: plan {label(t, chain.names)} gave {rows} rows"
            answer = rows
            name = label(t, chain.names)
            out.append({
                "sf": sf, "engine": engine.name, "chain": chain.name, "plan": name,
                "model_cost": model_cost(t, cost), "seconds": seconds, "rows": rows,
                **{f"is_{m}": name == p for m, p in chosen.items()},
            })

        engine.force_order(False)
        seconds, rows = timed(engine, chain.sql(left_deep(1, chain.n)), repeats)
        assert rows == answer
        out.append({
            "sf": sf, "engine": engine.name, "chain": chain.name, "plan": "engine optimizer",
            "model_cost": None, "seconds": seconds, "rows": rows,
            "is_dp": False, "is_greedy": False, "is_left_to_right": False,
        })
        log(f"  {engine.name} {chain.name}: {len(all_trees)} plans, {rows:,} rows")
    return out

