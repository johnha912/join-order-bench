"""
cost_model.py — CS 5800 Final Project, JOIN Order Optimization.
Owner: John.

Holds the size table and the cost functions. This module knows nothing about
dynamic programming, which is what lets dp.chain_dp stay generic.

Indexing: the lists that come in are 0-based; the table that goes out is
1-based, with row 0 and column 0 as unread padding.

Rounding convention (agreed, applies to heuristics.py too): a cardinality is an
integer, rounded ONCE from the exact product. Never round a value and then
multiply it again.
"""


def size_table(sizes, sel):
    """N[i][j] = number of rows produced by joining tables i..j.

    sizes: 0-based list, sizes[t] = |T_(t+1)|
    sel:   0-based list of length len(sizes)-1, sel[t] = selectivity of the
           edge between T_(t+1) and T_(t+2)

    Returns a 1-based table of whole row counts. Cardinalities are integers by
    convention, rounded ONCE from the exact product. The running float chain Nf
    is kept alongside so a rounded value is never fed back into the next
    multiplication: with sizes [3, 3, 3] and sel [0.5, 0.5], rounding at every
    step gives N[1][3] = 6, while the closed form on the slides gives 7.

    Theta(n^2) time and space.
    """
    n = len(sizes)
    assert len(sel) == n - 1, "a chain of n tables has n-1 edges"

    sz = [0] + list(sizes)       # sz[i] = |T_i|
    f = [0.0] + list(sel)        # f[i]  = selectivity of edge T_i - T_(i+1)

    N = [[0] * (n + 1) for _ in range(n + 1)]      # reported, integer
    Nf = [[0.0] * (n + 1) for _ in range(n + 1)]   # exact, never rounded
    for i in range(1, n + 1):
        N[i][i] = sz[i]
        Nf[i][i] = float(sz[i])
        for j in range(i + 1, n + 1):
            Nf[i][j] = Nf[i][j - 1] * sz[j] * f[j - 1]
            N[i][j] = round(Nf[i][j])
    return N


def join_cost(N, sel):
    """Build the cost(i, k, j) that chain_dp calls for the join problem.

    General CLRS form: N[i,k] * N[k+1,j] * f_k, the size of the last join.
    Under independent selectivities this equals N[i,j] for every k, so the
    optimization is entirely about the intermediates. The general form is kept
    anyway because it stays correct if independence is ever dropped.
    """
    f = [0.0] + list(sel)

    def cost(i, k, j):
        return round(N[i][k] * N[k + 1][j] * f[k])

    return cost


def matrix_cost(p):
    """CLRS 15.2 matrix-chain cost, used on Day 3 to validate the same DP.

    p is 0-based of length n+1, with A_i of dimension p[i-1] x p[i]. Here the
    cost genuinely depends on k, which is what makes matrix-chain the special
    case where the term factors into three boundary dimensions.
    """
    def cost(i, k, j):
        return p[i - 1] * p[k] * p[j]

    return cost
