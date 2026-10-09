import random
from math import comb

import duckdb
import pytest

from joinbench.chains import CHAINS, label, left_deep, model_cost, pick, trees
from joinbench.cost_model import join_cost, size_table
from joinbench.dp import chain_dp
from joinbench.pipeline import TABLES, generate


def catalan(n):
    return comb(2 * n, n) // (n + 1)


def test_dp_matches_brute_force():
    rng = random.Random(5800)
    for _ in range(300):
        n = rng.randint(2, 7)
        sizes = [rng.randint(1, 10**6) for _ in range(n)]
        sel = [1 / rng.randint(1, 10**4) for _ in range(n - 1)]
        names = [f"T{i}" for i in range(1, n + 1)]
        cost = join_cost(size_table(sizes, sel), sel)
        m, _ = chain_dp(n, cost)
        all_trees = list(trees(1, n))
        assert len(all_trees) == catalan(n - 1)
        assert m[1][n] == min(model_cost(t, cost) for t in all_trees)
        labels = {label(t, names) for t in all_trees}
        assert set(pick(sizes, sel, names).values()) <= labels


def test_chains_are_chains():
    for c in CHAINS:
        assert len(c.edges) == c.n - 1
        for k, (_, pk_table, _) in enumerate(c.edges):
            assert pk_table in c.tables[k:k + 2], f"{c.name} edge {k + 1}"


@pytest.fixture(scope="module")
def tpch(tmp_path_factory):
    raw = tmp_path_factory.mktemp("tpch")
    generate(0.01, raw)
    con = duckdb.connect()
    for t in TABLES:
        con.execute(f"CREATE VIEW {t} AS FROM '{(raw / f'{t}.parquet').as_posix()}'")
    return con


@pytest.mark.parametrize("chain", CHAINS, ids=lambda c: c.name)
def test_every_join_order_returns_the_same_answer(tpch, chain):
    tpch.execute("SET disabled_optimizers = 'join_order'")
    answers = {tpch.execute(chain.sql(t)).fetchone()[0] for t in trees(1, chain.n)}
    tpch.execute("RESET disabled_optimizers")
    assert answers == {tpch.execute(chain.sql(left_deep(1, chain.n))).fetchone()[0]}
