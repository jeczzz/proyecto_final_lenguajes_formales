"""FIRST, FOLLOW, LL(1) and SLR(1)."""

import argparse
import sys
from dataclasses import dataclass, field
from itertools import combinations

EPSILON = 'e'
END = '$'
START = 'S'
AUGMENTED = "S'"


class Grammar:
    def __init__(self, productions):
        self.productions = tuple(productions)
        self.by_head = {}
        for index, (head, body) in enumerate(self.productions):
            self.by_head.setdefault(head, []).append(index)
        self.terminals = {
            symbol for _, body in self.productions for symbol in body
            if symbol not in self.by_head
        }

    @classmethod
    def read(cls, stream):
        productions = []
        for _ in range(int(stream.readline())):
            head, alternatives = stream.readline().split('->', 1)
            productions.extend(
                (head.strip(), '' if body == EPSILON else body)
                for body in alternatives.split()
            )
        return cls(productions)


def first_sequence(sequence, first):
    result = set()
    for symbol in sequence:
        result.update(first[symbol] - {EPSILON})
        if EPSILON not in first[symbol]:
            return result
    result.add(EPSILON)
    return result


def first_follow(grammar):
    first = {symbol: {symbol} for symbol in grammar.terminals}
    first.update({head: set() for head in grammar.by_head})
    follow = {head: set() for head in grammar.by_head}
    follow[START].add(END)

    # Repeat until every production leaves the sets unchanged.
    changed = True
    while changed:
        changed = False
        for head, body in grammar.productions:
            added = first_sequence(body, first) - first[head]
            first[head].update(added)
            changed |= bool(added)

    changed = True
    while changed:
        changed = False
        for head, body in grammar.productions:
            for index, symbol in enumerate(body):
                if symbol not in follow:
                    continue
                suffix_first = first_sequence(body[index + 1:], first)
                candidates = suffix_first - {EPSILON}
                if EPSILON in suffix_first:
                    candidates.update(follow[head])
                added = candidates - follow[symbol]
                follow[symbol].update(added)
                changed |= bool(added)
    return first, follow


@dataclass
class Node:
    symbol: str
    production: int | None = None
    children: list = field(default_factory=list)
    attributes: dict = field(default_factory=dict)


class LL1:
    def __init__(self, grammar, first, follow):
        self.grammar = grammar
        self.table = {}
        self.conflicts = []
        for head, indices in grammar.by_head.items():
            alternatives = {
                index: first_sequence(grammar.productions[index][1], first)
                for index in indices
            }
            for left, right in combinations(indices, 2):
                left_first, right_first = alternatives[left], alternatives[right]
                overlap = left_first & right_first
                if EPSILON in left_first:
                    overlap |= (right_first - {EPSILON}) & follow[head]
                if EPSILON in right_first:
                    overlap |= (left_first - {EPSILON}) & follow[head]
                if overlap:
                    self.conflicts.append((head, left, right, overlap))
            for index, symbols in alternatives.items():
                lookaheads = symbols - {EPSILON}
                if EPSILON in symbols:
                    lookaheads.update(follow[head])
                for lookahead in sorted(lookaheads):
                    self.table.setdefault((head, lookahead), index)

    def parse(self, word, trace=None):
        if self.conflicts or not set(word) <= self.grammar.terminals:
            return None
        tokens = word + END
        root = Node(START)
        stack = [Node(END), root]
        position = 0
        while stack:
            if trace is not None:
                snapshot = ''.join(node.symbol for node in stack)
                remaining = tokens[position:]
            node = stack.pop()
            lookahead = tokens[position]
            if node.symbol in self.grammar.by_head:
                index = self.table.get((node.symbol, lookahead))
                if index is None:
                    return None
                head, body = self.grammar.productions[index]
                node.production = index
                node.children = [Node(symbol) for symbol in body]
                stack.extend(reversed(node.children))
                action = f'{head} -> {body or EPSILON}'
            elif node.symbol == lookahead:
                position += 1
                action = 'accept' if lookahead == END else f'match {lookahead}'
            else:
                return None
            if trace is not None:
                trace.append((snapshot, remaining, action))
        return root if position == len(tokens) else None


class SLR1:
    def __init__(self, grammar, follow):
        self.grammar = grammar
        self.productions = grammar.productions + ((AUGMENTED, START),)
        self.augmented = len(grammar.productions)
        self.states = [self.closure({(self.augmented, 0)})]
        state_ids = {self.states[0]: 0}
        self.transitions = {}
        for state_id, items in enumerate(self.states):
            symbols = {
                self.productions[index][1][dot]
                for index, dot in items if dot < len(self.productions[index][1])
            }
            for symbol in sorted(symbols):
                target = self.goto(items, symbol)
                if target not in state_ids:
                    state_ids[target] = len(self.states)
                    self.states.append(target)
                self.transitions[state_id, symbol] = state_ids[target]

        self.action = {}
        self.goto_table = {}
        self.conflicts = []
        for (state, symbol), target in self.transitions.items():
            if symbol in grammar.by_head:
                self.goto_table[state, symbol] = target
            else:
                self.add_action(state, symbol, ('shift', target))
        for state, items in enumerate(self.states):
            for index, dot in sorted(items):
                head, body = self.productions[index]
                if dot != len(body):
                    continue
                if index == self.augmented:
                    self.add_action(state, END, ('accept', None))
                else:
                    for lookahead in sorted(follow[head]):
                        self.add_action(state, lookahead, ('reduce', index))

    def closure(self, items):
        result = set(items)
        pending = list(result)
        while pending:
            index, dot = pending.pop()
            _, body = self.productions[index]
            if dot < len(body):
                for production in self.grammar.by_head.get(body[dot], ()):
                    item = (production, 0)
                    if item not in result:
                        result.add(item)
                        pending.append(item)
        return frozenset(result)

    def goto(self, items, symbol):
        return self.closure({
            (index, dot + 1) for index, dot in items
            if self.productions[index][1][dot:dot + 1] == symbol
        })

    def add_action(self, state, symbol, action):
        previous = self.action.setdefault((state, symbol), action)
        if previous != action:
            self.conflicts.append((state, symbol, previous, action))

    def parse(self, word):
        if self.conflicts or not set(word) <= self.grammar.terminals:
            return None
        tokens = word + END
        states = [0]
        nodes = []
        position = 0
        while True:
            lookahead = tokens[position]
            operation, value = self.action.get((states[-1], lookahead), (None, None))
            if operation == 'shift':
                states.append(value)
                nodes.append(Node(lookahead))
                position += 1
            elif operation == 'reduce':
                head, body = self.productions[value]
                size = len(body)
                children = []
                if size:
                    children = nodes[-size:]
                    del nodes[-size:]
                    del states[-size:]
                nodes.append(Node(head, value, children))
                states.append(self.goto_table[states[-1], head])
            elif operation == 'accept':
                return nodes[-1]
            else:
                return None


def words(stream):
    for line in stream:
        line = line.rstrip('\r\n')
        if not line:
            return
        yield '' if line == EPSILON else line


def print_sets(label, sets, nonterminals):
    for symbol in sorted(nonterminals):
        values = sets[symbol]
        ordered = sorted(values - {EPSILON, END})
        ordered.extend(marker for marker in (EPSILON, END) if marker in values)
        print(f'{label}({symbol}) = {{{", ".join(ordered)}}}')


def recognize(parser, stream):
    for word in words(stream):
        print('yes' if parser.parse(word) is not None else 'no')


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--sets', action='store_true')
    args = cli.parse_args()
    grammar = Grammar.read(sys.stdin)
    first, follow = first_follow(grammar)
    if args.sets:
        print_sets('First', first, grammar.by_head)
        print_sets('Follow', follow, grammar.by_head)
    ll = LL1(grammar, first, follow)
    slr = SLR1(grammar, follow)
    if not ll.conflicts and not slr.conflicts:
        while True:
            print('Select a parser (T: for LL(1), B: for SLR(1), Q: quit):')
            choice = sys.stdin.readline().strip()
            if choice in ('Q', ''):
                break
            if choice in ('T', 'B'):
                recognize(ll if choice == 'T' else slr, sys.stdin)
    elif not ll.conflicts:
        print('Grammar is LL(1).')
        recognize(ll, sys.stdin)
    elif not slr.conflicts:
        print('Grammar is SLR(1).')
        recognize(slr, sys.stdin)
    else:
        print('Grammar is neither LL(1) nor SLR(1).')


if __name__ == '__main__':
    main()
