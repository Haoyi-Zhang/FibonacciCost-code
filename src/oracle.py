"""Separate Bellman-Ford oracle: no import of the Dijkstra/saturation engine."""
def bellman(n, goals, edges, costs):
    h = [None] * n
    for g in goals:
        h[g] = 0
    # Every finite optimal path can be simple under nonnegative costs.
    for _ in range(n - 1):
        previous = h[:]
        for u, v, a in edges:
            if previous[v] is not None:
                z = costs[a] + previous[v]
                if h[u] is None or z < h[u]:
                    h[u] = z
        if h == previous:
            break
    if any(v is None for v in h):
        raise ValueError('outside finite-distance model')
    return tuple(h)


def partition(graphs, costs):
    left = list(costs)
    result = []
    for g in graphs:
        h = bellman(g.n, g.goals, g.edges, left)
        # Deliberately label-major, unlike candidate's edge-major reduction.
        allocated = tuple(max([0] + [h[u]-h[v] for u,v,b in g.edges if b==a])
                          for a in range(g.labels))
        result.append((tuple(left), h, allocated))
        left = [left[a] - allocated[a] for a in range(g.labels)]
    return tuple(result)
