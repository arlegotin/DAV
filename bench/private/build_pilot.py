"""Trusted, researcher-authored pilot definitions. Never an agent input/import.

Regenerate only before experimental freeze. Variants share a root, not a sample.
Each independent formulation is intentionally separate from its reference.
"""
from collections import Counter
import inspect
import itertools
import random
from pathlib import Path

from depverify.records import Task, canonical_json, sha256_bytes, to_dict, write_json_atomic


def ref_interval(x, p):
    if x['start'] > x['end']:
        return False
    left = x['value'] >= x['start'] if p['left'] else x['value'] > x['start']
    right = x['value'] <= x['end'] if p['right'] else x['value'] < x['end']
    return left and right


def enum_interval(x, p):
    members = set(range(x['start'] + (not p['left']), x['end'] + p['right']))
    return x['value'] in members


def ref_records(x, p):
    totals = {}
    for record in x['records']:
        amount = record['amount']
        eligible = amount > x['minimum'] if p['strict'] else amount >= x['minimum']
        if p['before'] and not eligible:
            continue
        totals[record['key']] = totals.get(record['key'], 0) + amount
    return [{'key': key, 'total': total} for key, total in totals.items()
            if p['before'] or (total > x['minimum'] if p['strict'] else total >= x['minimum'])]


def enum_records(x, p):
    eligible = [r for r in x['records'] if not p['before'] or
                (r['amount'] > x['minimum'] if p['strict'] else r['amount'] >= x['minimum'])]
    keys = list(dict.fromkeys(r['key'] for r in eligible))
    sums = [sum(r['amount'] for r in eligible if r['key'] == key) for key in keys]
    return [{'key': key, 'total': total} for key, total in zip(keys, sums)
            if p['before'] or (total > x['minimum'] if p['strict'] else total >= x['minimum'])]


def ref_sort(x, p):
    def key(r):
        score = -r['score'] if p['descending'] else r['score']
        return (score, r['name']) if p['name_ties'] else (score,)
    return [r['name'] for r in sorted(x, key=key)]


def enum_sort(x, p):
    remaining = list(enumerate(x))
    result = []
    while remaining:
        best = remaining[0]
        for item in remaining[1:]:
            a, b = item[1], best[1]
            better = a['score'] > b['score'] if p['descending'] else a['score'] < b['score']
            if a['score'] == b['score']:
                better = a['name'] < b['name'] if p['name_ties'] else item[0] < best[0]
            if better:
                best = item
        result.append(best[1]['name'])
        remaining.remove(best)
    return result


def ref_config(x, p):
    layers = ['defaults', 'environment', 'explicit'] if p['explicit_wins'] else ['defaults', 'explicit', 'environment']
    result = {}
    for layer in layers:
        for key, value in x[layer].items():
            if value is None:
                if p['delete_null']:
                    result.pop(key, None)
            else:
                result[key] = value
    return result


def enum_config(x, p):
    order = ['explicit', 'environment', 'defaults'] if p['explicit_wins'] else ['environment', 'explicit', 'defaults']
    result = {}
    for key in set().union(*(set(layer) for layer in x.values())):
        for layer in order:
            if key not in x[layer]:
                continue
            value = x[layer][key]
            if value is not None:
                result[key] = value
                break
            if p['delete_null']:
                break
    return result


def ref_parser(x, p):
    result = {}
    for line in x.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip().casefold() if p['fold'] else key.strip()
        if key and (p['last'] or key not in result):
            result[key] = value.strip()
    return result


def enum_parser(x, p):
    pairs = []
    for line in x.split('\n'):
        if line.lstrip().startswith('#'):
            continue
        pieces = line.split('=', 1)
        if len(pieces) == 2 and pieces[0].strip():
            key = pieces[0].strip()
            pairs.append((key.casefold() if p['fold'] else key, pieces[1].strip()))
    if not p['last']:
        pairs.reverse()
    return dict(pairs)


def ref_chunks(x, p):
    chunks = []
    remainder = []
    for start in range(0, len(x['items']), x['size']):
        chunk = x['items'][start:start + x['size']]
        if len(chunk) == x['size']:
            chunks.append(chunk)
        elif p['mode'] == 'partial':
            chunks.append(chunk)
        elif p['mode'] == 'pad':
            chunks.append(chunk + [None] * (x['size'] - len(chunk)))
        elif p['mode'] == 'carry':
            remainder = chunk
    return {'chunks': chunks, 'remainder': remainder}


def enum_chunks(x, p):
    full, tail = divmod(len(x['items']), x['size'])
    chunks = [[x['items'][n * x['size'] + k] for k in range(x['size'])] for n in range(full)]
    remainder = [x['items'][n] for n in range(full * x['size'], len(x['items']))]
    if tail and p['mode'] == 'partial':
        chunks.append(remainder)
    if tail and p['mode'] == 'pad':
        chunks.append(remainder + [None] * (x['size'] - tail))
    return {'chunks': chunks, 'remainder': remainder if p['mode'] == 'carry' else []}


def definitions():
    rng = random.Random(7301)
    intervals = [dict(zip(('start', 'end', 'value'), values)) for values in itertools.product(range(-2, 3), repeat=3)]
    records = [{'records': [{'key': rng.choice('abc'), 'amount': rng.randint(-3, 5)} for _ in range(n)],
                'minimum': rng.randint(-1, 3)} for n in range(33)]
    records += [{'records': [{'key': 'a', 'amount': 2}, {'key': 'b', 'amount': 2}], 'minimum': 2}]
    sorts = [[{'name': chr(97 + k), 'score': rng.randint(-2, 2)} for k in rng.sample(range(n), n)] for n in range(12)]
    sorts += [[{'name': 'b', 'score': 1}, {'name': 'a', 'score': 1}]]
    configs = [{layer: {k: rng.choice([None, 0, 1, 2]) for k in 'ab' if rng.random() < .8}
                for layer in ('defaults', 'environment', 'explicit')} for _ in range(32)]
    configs += [{'defaults': {'a': 1}, 'environment': {'a': None}, 'explicit': {}}]
    parsers = ['a=1\na=2', ' A = 1\na=2', 'a=x=y', '#comment\n\nb = z\nignored\n=empty', '']
    parsers += ['\n'.join(f'{rng.choice(["A", "a", "b"])}={rng.choice(["", "x=y", "2"])}' for _ in range(n)) for n in range(12)]
    chunks = [{'items': list(range(n)), 'size': size} for n, size in itertools.product(range(9), range(1, 5))]
    yield ('interval', [{'left': l, 'right': r} for l, r in itertools.product([False, True], repeat=2)],
           ref_interval, enum_interval, intervals,
           lambda p: f"Integer interval membership. Input is {{start:int,end:int,value:int}}. Return a JSON boolean. Left endpoint is {'included' if p['left'] else 'excluded'}; right endpoint is {'included' if p['right'] else 'excluded'}. A reversed interval is empty. Do not reorder endpoints.",
           "def solve(x):\n    return x['start'] < x['value'] < x['end']\n")
    yield ('records', [{'before': b, 'strict': s} for b, s in itertools.product([False, True], repeat=2)],
           ref_records, enum_records, records,
           lambda p: f"Aggregate integer amounts by string key. Input is {{records:[{{key:str,amount:int}}],minimum:int}}. {'Filter individual records before summing; keep all resulting groups' if p['before'] else 'Sum all records first, then filter group totals'}. The threshold comparison is {'strictly greater than' if p['strict'] else 'greater than or equal to'} minimum. Return [{{key:str,total:int}}] in first eligible key encounter order. Negative and zero amounts are valid. Empty input returns [].",
           "def solve(x):\n    totals={}\n    for r in x['records']:\n        totals[r['key']]=totals.get(r['key'],0)+r['amount']\n    return [{'key':k,'total':v} for k,v in totals.items() if v>x['minimum']]\n")
    yield ('sort', [{'descending': d, 'name_ties': t} for d, t in itertools.product([False, True], repeat=2)],
           ref_sort, enum_sort, sorts,
           lambda p: f"Input is a list of records {{name:str,score:int}} with unique ASCII names. Return all names ordered by score {'descending' if p['descending'] else 'ascending'}. Equal scores use {'name ascending' if p['name_ties'] else 'original input order'}. Do not mutate input. Empty input returns [].",
           "def solve(x):\n    return [r['name'] for r in sorted(x,key=lambda r:(r['score'],r['name']),reverse=True)]\n")
    yield ('config', [{'explicit_wins': e, 'delete_null': n} for e, n in itertools.product([False, True], repeat=2)],
           ref_config, enum_config, configs,
           lambda p: f"Input has defaults, environment, explicit maps with string keys and integer or null values. Merge from lowest to highest priority: {'defaults, environment, explicit' if p['explicit_wins'] else 'defaults, explicit, environment'}. A null value {'deletes an inherited key' if p['delete_null'] else 'is ignored, preserving inherited values'}. Later higher-priority integer values may recreate deleted keys. Return a map of integer values; key order is irrelevant. Missing keys do not override.",
           "def solve(x):\n    return x['defaults'] | x['environment'] | x['explicit']\n")
    yield ('parser', [{'fold': f, 'last': l} for f, l in itertools.product([False, True], repeat=2)],
           ref_parser, enum_parser, parsers,
           lambda p: f"Parse an input string of lines into a string-to-string map. Ignore blank lines, lines whose first nonspace character is #, lines without =, and empty keys. Split at the first = only; strip surrounding whitespace from keys and values. Keys {'are casefolded' if p['fold'] else 'remain case-sensitive'}. For duplicate normalized keys, {'last' if p['last'] else 'first'} value wins. An inline # is ordinary value data. Empty input returns {{}}.",
           "def solve(x):\n    out={}\n    for line in x.splitlines():\n        if '=' in line:\n            k,v=line.split('=')\n            out[k.strip()]=v.strip()\n    return out\n")
    yield ('chunks', [{'mode': mode} for mode in ('partial', 'drop', 'pad', 'carry')],
           ref_chunks, enum_chunks, chunks,
           lambda p: "Input is {items:[int],size:positive int}. Partition in input order into size-length chunks. Return {chunks:[[int or null]],remainder:[int]}. " +
               {'partial': 'Include a nonempty partial final chunk; remainder is [].',
                'drop': 'Discard an incomplete final chunk; remainder is [].',
                'pad': 'Pad a nonempty incomplete final chunk with null to size; remainder is [].',
                'carry': 'Do not include an incomplete final chunk; return its items in remainder.'}[p['mode']] +
               " Include every full chunk, including one ending exactly at the input length. Empty items gives no chunks and no remainder.",
           "def solve(x):\n    return {'chunks':[x['items'][i:i+x['size']] for i in range(0,len(x['items'])-x['size'],x['size'])], 'remainder':[]}\n")


def build():
    root = Path(__file__).resolve().parents[1]
    tasks = []
    for family, params, ref, independent, inputs, contract, original in definitions():
        for index, p in enumerate(params):
            episode = f'pilot-{family}-{index}'
            expected = [ref(x, p) for x in inputs]
            independent_expected = [independent(x, p) for x in inputs]
            assert canonical_json(expected) == canonical_json(independent_expected)
            # Two nonidentical public cases, selected without any model outputs.
            indices = [len(inputs) // 3, 2 * len(inputs) // 3]
            public = [{'input': inputs[i], 'expected': expected[i]} for i in indices]
            source = inspect.getsource(ref) + f'\ndef solve(x):\n    return {ref.__name__}(x, {p!r})\n'
            # The original closed/open bug must differ even in the all-open variant.
            bug = original
            if family == 'interval' and p == {'left': False, 'right': False}:
                bug = "def solve(x):\n    return x['start'] <= x['value'] <= x['end']\n"
            if family == 'records' and not p['before'] and p['strict']:
                bug = original.replace("v>x['minimum']", "v>=x['minimum']")
            text = contract(p)
            packets = {}
            # Both reviews use the same authored contract lineage: conservatively
            # label shared provenance even when filenames/prompt wording differ.
            for packet in ('A', 'B', 'D'):
                body = text if packet != 'D' else 'Local API contract version 2.\n' + text
                packets[packet] = {'body': body, 'source_id': f'{episode}-contract-{packet}',
                                   'lineage_id': episode + '-contract-v2', 'version': '2',
                                   'sha256': sha256_bytes(body.encode())}
            task = Task(episode, 'pilot-' + family, 'pilot', family, text,
                        'candidate.py', 'solve', {'candidate.py': bug, 'support.py': 'CONTRACT_VERSION = 2\n'},
                        public, {'packets': packets})
            constant = expected[indices[0]]
            examples = 'def solve(x):\n' + ''.join(f'    if x == {case["input"]!r}: return {case["expected"]!r}\n' for case in public) + f'    return {constant!r}\n'
            write_json_atomic(root / 'private/pilot' / (episode + '.json'),
                {'episode_id': episode, 'reference': source, 'inputs': inputs, 'expected': expected,
                 'independent_expected': independent_expected,
                 'mutants': {'boundary': bug, 'constant': f'def solve(x): return {constant!r}\n',
                             'public_example': examples}})
            tasks.append(task)
    public_path = root / 'public/pilot.jsonl'
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_bytes(b''.join(canonical_json(to_dict(t)) + b'\n' for t in tasks))
    write_json_atomic(root / 'public/pilot-manifest.json', {'schema_version': 1, 'episodes': 24,
        'root_groups': dict(Counter(t.root_group_id for t in tasks)), 'task_sha256': sha256_bytes(public_path.read_bytes()),
        'generation_seed': 7301, 'provenance_note': 'All pilot R1/R2 packets conservatively share the authored contract lineage.'})


if __name__ == '__main__':
    build()
