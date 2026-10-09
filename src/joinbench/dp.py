"""
dp.py - CS 5800 Final Project, JOIN Order Optimization.
Owner: John.

The DP engine, and nothing else. It never looks at table sizes, selectivities
or matrix dimensions: all of that is hidden behind the cost function that the
caller passes in. That is what lets the same code solve the join problem and
the CLRS 15.2 matrix-chain problem with one argument changed.

Indexing: m and s are 1-based, matching CLRS. Row 0 and column 0 are padding
and are never read. names is a plain 0-based list, so table i is names[i-1].

Tie-break (frozen on the Sunday call): when two split points cost the same,
keep the SMALLER k. The loop below uses a strict <, and k ascends, so the
first minimum found wins.
"""


def chain_dp(n, cost):
    """Bottom-up DP over a fixed-order chain of n items.

    cost(i, k, j) is the price of the LAST operation only: the one that merges
    block i..k with block k+1..j. Everything before it is already paid for by
    the two subproblems.

    Returns (m, s):
        m[i][j] = minimum total cost to combine items i..j
        s[i][j] = the split point k that achieves m[i][j]

    Recurrence:
        m[i][i] = 0
        m[i][j] = min over i <= k < j of  m[i][k] + m[k+1][j] + cost(i, k, j)

    Blocks are filled by increasing length, so both subproblems of a block are
    already final when the block is computed.

    Theta(n^3) time, Theta(n^2) space.
    """
    INF = float("inf")
    m = [[0] * (n + 1) for _ in range(n + 1)]
    s = [[0] * (n + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        m[i][i] = 0                                   # base case

    for length in range(2, n + 1):                    # block length
        for i in range(1, n - length + 2):
            j = i + length - 1
            m[i][j] = INF
            for k in range(i, j):                     # ascending, so a tie
                q = m[i][k] + m[k + 1][j] + cost(i, k, j)
                if q < m[i][j]:                       # keeps the smaller k
                    m[i][j] = q
                    s[i][j] = k
    return m, s


def build_order(s, i, j, names):
    """Rebuild the fully parenthesized order from the split table.

    CLRS PRINT-OPTIMAL-PARENS, returning a string instead of printing. The
    separator and spacing are frozen: "((C |x| O) |x| (OI |x| (P |x| Cat)))".

    Theta(n) time - one call per item, one per internal node.
    """
    if i == j:
        return names[i - 1]
    k = s[i][j]
    left = build_order(s, i, k, names)
    right = build_order(s, k + 1, j, names)
    return f"({left} |x| {right})"
