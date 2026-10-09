# heuristics.py - CS 5800 Final Project. Owner: Elliot.
# The two shortcuts the DP is compared against.
# Both call cost_model.join_cost - the SAME cost function chain_dp is handed -
# so any difference in totals is a difference in the ORDER chosen and nothing
# else. That is the whole basis of the comparison, so neither function is ever
# given a cost model of its own.
# sizes/sel/names arrive 0-based from CASES; the table N is 1-based.
# names is optional; without it the order string falls back to T1..Tn.
from .cost_model import size_table, join_cost
def _labels(names, n):
    # Names as a 1-based list, so label[i] is the name of table i.
    if names is None:
        names = ["T%d" % t for t in range(1, n + 1)]
    assert len(names) == n, "need exactly one name per table"
    return [None] + list(names)
def left_to_right(sizes, sel, names=None):
    # Join in schema order: (((T1 |x| T2) |x| T3) ... |x| Tn).
    # No decisions at all - the plan an engine produces if it just follows the
    # FROM clause. Theta(n) joins on top of the Theta(n^2) spent building N.
    n = len(sizes)
    N = size_table(sizes, sel)
    cost = join_cost(N, sel)
    label = _labels(names, n)
    total = 0
    order = label[1]
    for j in range(2, n + 1):
        total += cost(1, j - 1, j)
        order = "(" + order + " |x| " + label[j] + ")"
    return total, order
def greedy(sizes, sel, names=None):
    # Merge the adjacent pair whose RESULT is smallest, and repeat.
    # Looks one join ahead and no further. Leftmost pair wins a tie, which is
    # the smallest-k rule carried over. O(n^2): n-1 merges, n-1 pairs scanned.
    n = len(sizes)
    N = size_table(sizes, sel)
    cost = join_cost(N, sel)
    label = _labels(names, n)
    blocks = [(t, t, label[t]) for t in range(1, n + 1)]
    total = 0
    while len(blocks) > 1:
        best_p, best_rows = 0, None
        for p in range(len(blocks) - 1):
            rows = N[blocks[p][0]][blocks[p + 1][1]]
            if best_rows is None or rows < best_rows:
                best_p, best_rows = p, rows
        a, b = blocks[best_p], blocks[best_p + 1]
        total += cost(a[0], a[1], b[1])
        merged = (a[0], b[1], "(" + a[2] + " |x| " + b[2] + ")")
        blocks = blocks[:best_p] + [merged] + blocks[best_p + 2:]
    return total, blocks[0][2]
