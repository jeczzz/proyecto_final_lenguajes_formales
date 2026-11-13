"""Generic dependency-graph evaluator and a sensor-calibration SDD."""

import argparse
import sys
from collections import deque
from dataclasses import dataclass
from typing import Callable

from parsers import Grammar, LL1, first_follow, words


@dataclass(frozen=True)
class Rule:
    # Position 0 is the head. Positions 1, 2, ... are body occurrences.
    target: tuple[int, str]
    sources: tuple[tuple[int, str], ...]
    compute: Callable


class CircularSDD(Exception):
    pass


def evaluate(tree, rules):
    nodes = [tree]
    depth = [0]
    positions = {id(tree): 0}
    # Number nodes in preorder, without using the Python call stack.
    pending = [(child, 1) for child in reversed(tree.children)]
    while pending:
        node, level = pending.pop()
        positions[id(node)] = len(nodes)
        nodes.append(node)
        depth.append(level)
        pending.extend((child, level + 1) for child in reversed(node.children))

    incoming = {}
    outgoing = {}
    known = {}
    definitions = {}

    def add_vertex(vertex):
        if vertex not in incoming:
            incoming[vertex] = 0
            outgoing[vertex] = []

    for index, node in enumerate(nodes):
        if node.production is None:
            vertex = (index, 'lexval')
            add_vertex(vertex)
            known[vertex] = node.symbol
            continue
        occurrences = (index, *(positions[id(child)] for child in node.children))
        for rule in rules[node.production]:
            target_position, target_name = rule.target
            target = (occurrences[target_position], target_name)
            sources = tuple((occurrences[pos], name) for pos, name in rule.sources)
            if target in definitions:
                raise ValueError(f'Duplicate attribute definition: {target}')
            definitions[target] = (sources, rule.compute)
            add_vertex(target)
            for source in dict.fromkeys(sources):
                add_vertex(source)
                outgoing[source].append(target)
                incoming[target] += 1

    ready = deque(vertex for vertex, count in incoming.items() if count == 0)
    order = []
    while ready:
        vertex = ready.popleft()
        order.append(vertex)
        for target in outgoing[vertex]:
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
    if len(order) != len(incoming):
        raise CircularSDD

    values = known.copy()
    for vertex in order:
        if vertex in definitions:
            sources, compute = definitions[vertex]
            values[vertex] = compute(*(values[source] for source in sources))
        index, name = vertex
        nodes[index].attributes[name] = values[vertex]
    return nodes, depth, order


def identity(value):
    return value


# Ideal sensor model: raw signal = gain * calibrated reading.
LOW_GAIN = 2
HIGH_GAIN = 4
RAW_SIGNALS = {'a': 8, 'b': 12}


def select_gain(command):
    return HIGH_GAIN if command == 'h' else LOW_GAIN


def calibrate(gain, command):
    return RAW_SIGNALS[command] / gain


def add_readings(current, remaining):
    return current + remaining


PRODUCTIONS = (
    ('S', 'R'), ('R', 'CR'), ('R', 'MR'), ('R', ''),
    ('C', 'h'), ('C', 'l'), ('M', 'a'), ('M', 'b'),
)

GAIN_RULES = (Rule((0, 'gain'), ((1, 'lexval'),), select_gain),)
READING_RULES = (
    Rule((0, 'value'), ((0, 'gain'), (1, 'lexval')), calibrate),
)

SENSOR_RULES = (
    (Rule((1, 'gain'), (), lambda: LOW_GAIN),
     Rule((0, 'total'), ((1, 'total'),), identity)),
    (Rule((2, 'gain'), ((1, 'gain'),), identity),
     Rule((0, 'total'), ((2, 'total'),), identity)),
    (Rule((1, 'gain'), ((0, 'gain'),), identity),
     Rule((2, 'gain'), ((0, 'gain'),), identity),
     Rule((0, 'total'), ((1, 'value'), (2, 'total')), add_readings)),
    (Rule((0, 'total'), (), lambda: 0.0),),
    GAIN_RULES,
    GAIN_RULES,
    READING_RULES,
    READING_RULES,
)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--circular', action='store_true',
                     help='Make the initial R.gain depend on R.total in S -> R')
    args = cli.parse_args()
    grammar = Grammar(PRODUCTIONS)
    parser = LL1(grammar, *first_follow(grammar))
    rules = list(SENSOR_RULES)
    if args.circular:
        rules[0] = (Rule((1, 'gain'), ((1, 'total'),), identity), rules[0][1])
    for word in words(sys.stdin):
        tree = parser.parse(word)
        if tree is None:
            print('no')
            continue
        try:
            nodes, depth, order = evaluate(tree, rules)
        except CircularSDD:
            print('SDD is circular.')
            return
        print('Annotated parse tree:')
        for index, node in enumerate(nodes):
            attrs = ', '.join(f'{key}={value!r}' for key, value in sorted(node.attributes.items()))
            print(f'{"  " * depth[index]}{node.symbol}{index} [{attrs}]')
        print('Evaluation order:')
        print(' -> '.join(f'{nodes[index].symbol}{index}.{name}' for index, name in order))
        print(f'Main attribute S.total = {tree.attributes["total"]}')


if __name__ == '__main__':
    main()
