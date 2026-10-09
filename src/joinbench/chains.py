"""Chain queries over TPC-H, every join tree for them, and the SQL for each tree.

A tree is a table index (1-based, matching dp.py) or a pair (left, right) of
trees over two adjacent spans. Every tree of a chain returns the same rows; only
the intermediate results differ, which is what the benchmark measures.
"""

from dataclasses import dataclass, field

from .cost_model import join_cost, size_table
from .dp import build_order, chain_dp
from .heuristics import greedy, left_to_right

LABELS = {
    "region": "R", "nation": "N", "customer": "C", "orders": "O",
    "lineitem": "L", "part": "P", "supplier": "S", "partsupp": "PS",
}


@dataclass
class Chain:
    name: str
    tables: list[str]
    # edges[k-1] joins tables[k-1] and tables[k]: (fk column, pk table, pk column)
    edges: list[tuple[str, str, str]]
    filters: dict[str, str] = field(default_factory=dict)

    @property
    def n(self):
        return len(self.tables)

    @property
    def names(self):
        return [LABELS[t] for t in self.tables]

    def from_clause(self, t):
        if isinstance(t, int):
            return self.tables[t - 1]
        left, right = t
        fk, _, pk = self.edges[span(left)[1] - 1]
        return f"({self.from_clause(left)} JOIN {self.from_clause(right)} ON {fk} = {pk})"

    def sql(self, t):
        lo, hi = span(t)
        preds = [self.filters[x] for x in self.tables[lo - 1:hi] if x in self.filters]
        where = f" WHERE {' AND '.join(preds)}" if preds else ""
        return f"SELECT count(*) FROM {self.from_clause(t)}{where}"


CHAINS = [
    Chain(
        "brass_parts_europe_1995",
        ["part", "lineitem", "orders", "customer", "nation", "region"],
        [("l_partkey", "part", "p_partkey"), ("l_orderkey", "orders", "o_orderkey"),
         ("o_custkey", "customer", "c_custkey"), ("c_nationkey", "nation", "n_nationkey"),
         ("n_regionkey", "region", "r_regionkey")],
        {"part": "p_type LIKE '%BRASS'",
         "orders": "o_orderdate >= DATE '1995-01-01' AND o_orderdate < DATE '1996-01-01'",
         "region": "r_name = 'EUROPE'"},
    ),
    Chain(
        "asia_suppliers_1994",
        ["region", "nation", "supplier", "lineitem", "orders"],
        [("n_regionkey", "region", "r_regionkey"), ("s_nationkey", "nation", "n_nationkey"),
         ("l_suppkey", "supplier", "s_suppkey"), ("l_orderkey", "orders", "o_orderkey")],
        {"region": "r_name = 'ASIA'",
         "orders": "o_orderdate >= DATE '1994-01-01' AND o_orderdate < DATE '1995-01-01'"},
    ),
    Chain(  # the join path of TPC-H Q2
        "min_cost_supplier",
        ["region", "nation", "supplier", "partsupp", "part"],
        [("n_regionkey", "region", "r_regionkey"), ("s_nationkey", "nation", "n_nationkey"),
         ("ps_suppkey", "supplier", "s_suppkey"), ("ps_partkey", "part", "p_partkey")],
        {"region": "r_name = 'EUROPE'", "part": "p_size = 15 AND p_type LIKE '%BRASS'"},
    ),
    Chain(  # the join path of TPC-H Q10
        "returned_items",
        ["nation", "customer", "orders", "lineitem"],
        [("c_nationkey", "nation", "n_nationkey"), ("o_custkey", "customer", "c_custkey"),
         ("l_orderkey", "orders", "o_orderkey")],
        {"orders": "o_orderdate >= DATE '1993-10-01' AND o_orderdate < DATE '1994-01-01'",
         "lineitem": "l_returnflag = 'R'"},
    ),
]


def trees(i, j):
    """Every binary join tree over tables i..j: Catalan(j - i) of them."""
    if i == j:
        yield i
        return
    for k in range(i, j):
        for left in trees(i, k):
            for right in trees(k + 1, j):
                yield (left, right)


def left_deep(i, j):
    return i if i == j else (left_deep(i, j - 1), j)


def span(t):
    if isinstance(t, int):
        return t, t
    return span(t[0])[0], span(t[1])[1]


def label(t, names):
    """Same string format as dp.build_order, so plans can be matched by label."""
    if isinstance(t, int):
        return names[t - 1]
    return f"({label(t[0], names)} |x| {label(t[1], names)})"


def model_cost(t, cost):
    """Sum of every join's output size under the cost model (what chain_dp minimizes)."""
    if isinstance(t, int):
        return 0
    (lo, k), (_, hi) = span(t[0]), span(t[1])
    return model_cost(t[0], cost) + model_cost(t[1], cost) + cost(lo, k, hi)


def pick(sizes, sel, names):
    """Labels of the plans chosen by the DP and the two v1 heuristics."""
    n = len(sizes)
    _, s = chain_dp(n, join_cost(size_table(sizes, sel), sel))
    return {
        "dp": build_order(s, 1, n, names),
        "greedy": greedy(sizes, sel, names)[1],
        "left_to_right": left_to_right(sizes, sel, names)[1],
    }
