"""Algorithmic synthetic finite-domain planning families, authored for this study.

Operators are total coordinate maps, so projecting a coordinate subset exactly
commutes with application. Identity transitions are represented explicitly.
No downloaded benchmark, learned demonstration or hidden dataset is used.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from random import Random
from cascades import Graph

@dataclass(frozen=True)
class Task:
    q: int
    dims: int
    actions: tuple[tuple[tuple[int, int], ...], ...]  # (coordinate, saturating step)
    costs: tuple[int, ...]
    patterns: tuple[tuple[int, ...], ...]
    start: tuple[int, ...]

    @property
    def goal(self):
        return (self.q-1,) * self.dims

    def successors(self, s):
        result = []
        for a, changes in enumerate(self.actions):
            t = list(s)
            for j, step in changes:
                t[j] = max(0, min(self.q-1, s[j]+step))
            # A* need not enqueue an identity successor under nonnegative costs.
            if tuple(t) != s:
                result.append((a, tuple(t)))
        return result

    def abstractions(self):
        graphs = []
        for pattern in self.patterns:
            states = list(product(range(self.q), repeat=len(pattern)))
            ids = {s:i for i,s in enumerate(states)}
            pos = {j:k for k,j in enumerate(pattern)}
            edges = []
            for i,s in enumerate(states):
                for a,changes in enumerate(self.actions):
                    t = list(s)
                    for j,step in changes:
                        if j in pos:
                            k = pos[j]
                            t[k] = max(0, min(self.q-1, s[k]+step))
                    edges.append((i,ids[tuple(t)],a))
            graphs.append(Graph(len(states),len(self.actions),(len(states)-1,),tuple(edges)))
        return tuple(graphs)

    def heuristic(self,tables,combine='sum'):
        hs = [t.h if hasattr(t,'h') else t for t in tables]
        patterns,q = self.patterns,self.q
        def evaluate(s):
            values=[]
            for p,h in zip(patterns,hs):
                idx=0
                for j in p:
                    idx=idx*q+s[j]
                values.append(h[idx])
            return sum(values) if combine=='sum' else max(values)
        return evaluate


def make_task(family,q,seed):
    rng=Random(seed)
    n=4 if family=='independent' else 5
    actions=[];cost=[]
    for j in range(n):
        a=rng.randrange(2,6)
        actions.extend((((j,1),),((j,1),),((j,-1),)))
        cost.extend((a,a+4,1))
    if family=='coupled':
        for j in range(n):
            actions.append(((j,1),((j+1)%n,1)))
            cost.append(rng.randrange(2,8))
        patterns=[(j,(j+1)%n) for j in range(n)]
    elif family=='independent':
        patterns=[(j,) for j in range(n)]
    else:
        raise ValueError('unknown family')
    rng.shuffle(patterns)
    return Task(q,n,tuple(actions),tuple(cost),tuple(patterns),(0,)*n)


def relay_task(m,delta):
    actions=[]
    for a in range(m+1):
        actions.append(tuple((j,1) for j in (a-1,a) if 0<=j<m))
    return Task(2,m,tuple(actions),(4,)+(8,)*m,tuple((j,) for j in range(m)),(0,)*m)


def changed_costs(task,mode,seed,delta=None):
    c=list(task.costs)
    if mode=='relay':
        c[0]-=delta
        return tuple(c)
    rng=Random(10000+seed)
    # Uniformly select a label, not a cost-slack-filtered or result-filtered label.
    a=rng.randrange(len(c))
    c[a]=max(0,c[a]-rng.randrange(1,7))
    if mode=='mixed':
        b=rng.choice([j for j in range(len(c)) if j!=a])
        c[b]+=rng.randrange(1,5)
    return tuple(c)



def fibonacci(n):
    """Return F_n for F_1 = F_2 = 1 (and F_0 = 0)."""
    if type(n) is not int or n < 0:
        raise ValueError('n must be a nonnegative integer')
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def fibonacci_amplifier_task(k):
    """A bounded-incidence Fibonacci residual amplifier.

    The task has 2*k+3 singleton patterns and 2*k+4 action labels. Decreasing
    only label 0 from 1 to 0 changes every table and leaves one final residual
    perturbation F_(k+3).  Every action affects at most three patterns, every
    pattern has at most three advancing labels, and perturbation support is at
    most two.  These are exact-integer proof witnesses, not timing cases.
    """
    if type(k) is not int or not 0 <= k <= 256:
        raise ValueError('the materialized witness generator supports 0 <= k <= 256')

    # Initializer: old costs (d,x,y)=(1,1,2).  After d decreases to zero,
    # the active pair has old residuals (0,1) and differences (1,1).
    costs = [1, 1, 2]
    supports = [(0, 1, 2)]
    big, small = 1, 2
    A = B = 1

    # Two patterns map the carry pair (A,B) to (A+B,A).
    for _ in range(k):
        z, w = len(costs), len(costs) + 1
        costs.extend((A, 2 * A + B))
        supports.extend(((big, z), (small, z, w)))
        big, small = small, w
        A, B = A + B, A

    # Two-pattern cleanup turns the active pair into one final difference A+B.
    z = len(costs)
    costs.append(A)
    supports.extend(((big, z), (small, z)))

    actions = tuple(
        tuple((i, 1) for i, support in enumerate(supports) if a in support)
        for a in range(len(costs))
    )
    n = len(supports)
    task = Task(2, n, actions, tuple(costs), tuple((i,) for i in range(n)), (0,) * n)
    return task, small
