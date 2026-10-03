"""Single prospective replacement: six fresh roots, explicit bounded domains.

Trusted benchmark construction only. Candidate code is never executed on the host.
References are ordinary functions written here; independent expectations use a
different formulation. All candidate/reference/mutant execution uses the runner.
"""
import inspect
import itertools
import json
from pathlib import Path

from depverify.records import Task, canonical_json, sha256_bytes, to_dict, write_json_atomic


def runs(x, variant):
    out=[]
    for value in x:
        if out and out[-1][0]==value:out[-1][1]+=1
        else:out.append([value,1])
    if variant>=2:out=[item for item in out if item[1]>=2]
    if variant%2:out=[item[::-1] for item in out]
    return out


def quotient(x, variant):
    a,b=x['a'],x['b']
    if variant==0:q=a//b
    elif variant==1:q=-((-a)//b)
    elif variant==2:q=(abs(a)//abs(b))*(-1 if (a<0)!=(b<0) else 1)
    else:q=(a-(a%abs(b)))//b
    return {'q':q,'r':a-b*q}


def reach(x, variant):
    seen={x['start']};todo=[x['start']]
    while todo:
        node=todo.pop()
        for a,b in x['edges']:
            targets=[]
            if a==node:targets.append(b)
            if variant>=2 and b==node:targets.append(a)
            for target in targets:
                if target not in seen:seen.add(target);todo.append(target)
    if variant%2==0:seen.discard(x['start'])
    return sorted(seen)


def escape(x, variant):
    table={'&':'&amp;','<':'&lt;','>':'&gt;'}
    if variant&1:table['"']='&quot;'
    if variant&2:table["'"]='&#39;'
    return ''.join(table.get(c,c) for c in x)


def queue(x, variant):
    items=[];out=[]
    for command in x['commands']:
        op=command['op']
        if op=='push':
            accepted=x['capacity']>0 and (len(items)<x['capacity'] or variant>=2)
            if accepted:
                if len(items)==x['capacity']:items.pop(0)
                items.append(command['value'])
            out.append(accepted)
        elif op=='pop':out.append(items.pop(-1 if variant%2 else 0) if items else None)
        else:out.append(items[-1 if variant%2 else 0] if items else None)
    return out


def migration(x, variant):
    from support import encode_v2
    return encode_v2(x,keep_zero=bool(variant&1),layout='pairs' if variant&2 else 'objects')


API='''API_VERSION = 2
def encode_v2(values, *, keep_zero, layout):
    items = []
    for i, n in enumerate(values):
        if keep_zero or n != 0:
            items.append([i, n] if layout == "pairs" else {"index": i, "value": n})
    return {"version": 2, "items": items}
'''


def independent(kind,x,v):
    if kind=='runs':
        pairs=[[key,len(list(group))] for key,group in itertools.groupby(x)]
        return [(p[::-1] if v%2 else p) for p in pairs if v<2 or p[1]>=2]
    if kind=='quotient':
        from fractions import Fraction
        import math
        ratio=Fraction(x['a'],x['b'])
        if v<3:q=(math.floor,math.ceil,math.trunc)[v](ratio)
        else:
            choices=[q for q in range(-100,101) if 0<=x['a']-x['b']*q<abs(x['b'])]
            assert len(choices)==1
            q=choices[0]
        return {'q':q,'r':x['a']-x['b']*q}
    if kind=='reach':
        nodes=sorted({x['start'],*(a for a,b in x['edges']),*(b for a,b in x['edges'])})
        links={(a,b) for a,b in x['edges']}
        if v>=2:links|={(b,a) for a,b in x['edges']}
        links|={(n,n) for n in nodes}
        for mid in nodes:
            links|={(a,b) for a in nodes for b in nodes if (a,mid) in links and (mid,b) in links}
        return [n for n in nodes if (x['start'],n) in links and (v%2 or n!=x['start'])]
    if kind=='escape':
        mapping={ord('&'):'&amp;',ord('<'):'&lt;',ord('>'):'&gt;'}
        if v&1:mapping[ord('"')]='&quot;'
        if v&2:mapping[ord("'")]='&#39;'
        return x.translate(mapping)
    if kind=='queue':
        from collections import deque
        state=deque();responses=[]
        for c in x['commands']:
            if c['op']=='push':
                if x['capacity']==0 or (len(state)>=x['capacity'] and v<2):responses.append(False)
                else:
                    if len(state)==x['capacity']:state.popleft()
                    state.append(c['value']);responses.append(True)
            elif c['op']=='peek':responses.append((state[-1] if v%2 else state[0]) if state else None)
            else:responses.append((state.pop() if v%2 else state.popleft()) if state else None)
        return responses
    return {'version':2,'items':[[i,n] if v&2 else {'index':i,'value':n} for i,n in enumerate(x) if v&1 or n!=0]}


def domains():
    lists=[list(x) for n in range(5) for x in itertools.product(('a','b'),repeat=n)]
    numbers=[{'a':a,'b':b} for a in range(-20,21) for b in (-5,-2,-1,1,2,5)]
    edge_options=[['a','b'],['b','c'],['c','a'],['c','d']]
    graphs=[{'edges':[e for i,e in enumerate(edge_options) if mask&(1<<i)],'start':s}
            for mask in range(16) for s in ('a','b','absent')]
    strings=[''.join(x) for n in range(4) for x in itertools.product(('a','&','<','>','"',"'"),repeat=n)]
    command_options=[{'op':'push','value':'a'},{'op':'push','value':'b'},{'op':'pop'},{'op':'peek'}]
    queues=[{'capacity':cap,'commands':list(commands)} for cap in range(4) for n in range(4)
            for commands in itertools.product(command_options,repeat=n)]
    integers=[list(x) for n in range(4) for x in itertools.product((-1,0,2),repeat=n)]
    return {'runs':lists,'quotient':numbers,'reach':graphs,'escape':strings,'queue':queues,'migration':integers}


def contracts(kind,v):
    common=' Return JSON-compatible values. Do not modify the input. Change only candidate.py.'
    if kind=='runs':
        text=('solve(x) receives a list of strings. Encode consecutive equal runs, preserving run order. '
              f'Return each run as {"[count, value]" if v%2 else "[value, count]"}. '
              f'{"Omit runs of length 1." if v>=2 else "Include runs of every length."} Empty input returns [].')
    elif kind=='quotient':
        rounding=('floor (toward negative infinity)','ceiling (toward positive infinity)','truncation toward zero',
                  'the unique quotient with 0 <= remainder < abs(b)')[v]
        text=f'solve(x) receives {{"a": integer -20..20, "b": nonzero integer -5..5}}. Return {{"q": quotient, "r": remainder}} with a = b*q + r. Choose q by {rounding}. Handle negative a and negative b.'
    elif kind=='reach':
        text=(f'solve(x) receives {{"edges": list of [node, node], "start": node}}. Nodes are strings. Edges are {"undirected" if v>=2 else "directed from first to second"}. '
              'Return sorted distinct nodes reachable by paths of any length, including cycles. '
              f'{"Include" if v%2 else "Always exclude"} the start node in the result, even if it has no edges.')
    elif kind=='escape':
        text=('solve(x) receives a string. Escape original & as &amp;, < as &lt;, > as &gt;. '
              f'{"Escape double quotes as &quot;." if v&1 else "Leave double quotes unchanged."} '
              f'{"Escape apostrophes as &#39;." if v&2 else "Leave apostrophes unchanged."} '
              'Preserve all other characters and their order. Process each original character once; do not escape generated entities.')
    elif kind=='queue':
        text=(f'solve(x) receives {{"capacity": nonnegative integer, "commands": list of commands}}. Start with empty storage. '
              'push has a string value; pop and peek have no value. Return one response per command. '
              f'Use {"LIFO: newest" if v%2 else "FIFO: oldest"} for pop/peek. Empty pop/peek returns null. '
              f'When full, {"drop the oldest stored value before accepting a push" if v>=2 else "reject a push without changing storage"}. '
              'push returns a boolean for acceptance. Capacity 0 rejects every push. peek does not remove an item.')
    else:
        text=(f'Migrate solve(x), for a list of integers, from local API version 1 to version 2 in immutable support.py. '
              f'Use encode_v2 with keep_zero={bool(v&1)} and layout={"pairs" if v&2 else "objects"}. '
              'Return its version-2 object. Preserve original input indices when zeros are omitted; no index renumbering. '
              'The old encode_v1 function is unavailable in version 2. All API code is provided.')
    return text+common


def source(reference,v):
    name=reference.__name__
    return inspect.getsource(reference).replace(f'def {name}(x, variant):',f'def solve(x):\n    variant={v}')


def main():
    root=Path(__file__).resolve().parents[2];tasks=[];private_hashes={}
    functions={'runs':runs,'quotient':quotient,'reach':reach,'escape':escape,'queue':queue,'migration':migration}
    originals={
        'runs':'def solve(x):\n    return [[v,1] for v in x]\n',
        'quotient':'def solve(x):\n    q=abs(x["a"])//abs(x["b"])\n    return {"q":q,"r":x["a"]-x["b"]*q}\n',
        'reach':'def solve(x):\n    return sorted({b for a,b in x["edges"] if a==x["start"]})\n',
        'escape':'def solve(x):\n    return x.replace("<","&lt;").replace("&","&amp;")\n',
        'queue':'def solve(x):\n    items=[];out=[]\n    for c in x["commands"]:\n        if c["op"]=="push":items.append(c["value"]);out.append(None)\n        elif c["op"]=="pop":out.append(items.pop(0) if items else None)\n        else:out.append(items[0] if items else None)\n    return out\n',
        'migration':'def solve(x):\n    from support import encode_v1\n    return encode_v1(x)\n'}
    examples={
        'runs':[[],['a','a','b'],['b','a','a','b','b']],
        'quotient':[{'a':7,'b':3},{'a':-7,'b':3},{'a':7,'b':-3}],
        'reach':[{'edges':[],'start':'a'},{'edges':[['a','b'],['b','c']],'start':'a'},
                 {'edges':[['b','a']],'start':'a'}],
        'escape':['a&b','<x>',"'\""],
        'queue':[{'capacity':0,'commands':[{'op':'push','value':'x'},{'op':'pop'}]},
                 {'capacity':1,'commands':[{'op':'push','value':'a'},{'op':'push','value':'b'},{'op':'peek'},{'op':'pop'},{'op':'pop'}]},
                 {'capacity':2,'commands':[{'op':'push','value':'a'},{'op':'push','value':'b'},{'op':'pop'}]}],
        'migration':[[],[0,2],[1,0,-1]]}
    for kind,inputs in domains().items():
        for v in range(4):
            reference=source(functions[kind],v)
            expected=[independent(kind,x,v) for x in inputs]
            # Migration reference calls public support; its independent oracle
            # is checked later against actual isolated execution, never host exec.
            if kind!='migration':assert [functions[kind](x,v) for x in inputs]==expected
            contract=contracts(kind,v);eid=f'replacement-{kind}-{v}'
            initial=('Local API v1: encode_v1(values) returned an unversioned list. The issue requests migration to v2; use the provided v2 code.'
                     if kind=='migration' else 'Local behavior specification version 1.\n'+contract)
            grounded=('Local API v2: encode_v2(values, *, keep_zero, layout). layout is objects or pairs; keep_zero controls omission of zeros. '
                      'Return {version: 2, items: ...}; each item retains its original input index. Keyword arguments are mandatory.'
                      if kind=='migration' else 'Local contract version 1, with explicit boundary semantics.\n'+contract)
            packets={name:{'source_id':f'{kind}-'+('api-v2' if name=='D' else 'initial'),
                          'lineage_id':f'local-{kind}-specification','version':'2' if kind=='migration' and name=='D' else '1',
                          'body':body,'sha256':sha256_bytes(body.encode())}
                     for name,body in [('A',initial),('B',initial),('D',grounded)]}
            public=tuple({'input':x,'expected':independent(kind,x,v)} for x in examples[kind])
            task=Task(eid,'replacement-'+kind,'pilot',kind,contract,'candidate.py','solve',
                {'candidate.py':originals[kind],'support.py':API if kind=='migration' else 'CONTRACT_VERSION = 1\n'},
                public,{'packets':packets,'requirements':{'input_immutable':True},'revision':'interface-v1'})
            if kind in ('runs','escape','migration'):change='    x=x[:-1]\n'
            elif kind=='quotient':change='    x=dict(x);x["a"]+=1\n'
            elif kind=='reach':change='    x=dict(x);x["edges"]=x["edges"][:-1]\n'
            else:change='    x=dict(x);x["capacity"]=0\n'
            lookup={json.dumps(p['input'],sort_keys=True):p['expected'] for p in public}
            mutants={'boundary':reference.replace('def solve(x):\n','def solve(x):\n'+change,1),
                     'constant':'def solve(x):\n    return []\n',
                     'public_example_only':'def solve(x):\n    import json\n    values='+repr(lookup)+'\n    return values.get(json.dumps(x,sort_keys=True))\n'}
            if kind!='escape':
                mutation=('    original=x; x=list(x); original.append("mutation")\n' if kind in ('runs','migration')
                          else '    original=x; x=dict(x); original["mutation"]=True\n')
                mutants['input_mutation']=reference.replace('def solve(x):\n','def solve(x):\n'+mutation,1)
            case={'episode_id':eid,'inputs':inputs,'expected':expected,'independent_expected':expected,
                  'reference':reference,'mutants':mutants,'domain':'Explicit deterministic small-domain enumeration; see constructor and contract.'}
            path=root/'bench/private/replacement-pilot'/(eid+'.json');write_json_atomic(path,case)
            private_hashes[eid]=sha256_bytes(path.read_bytes());tasks.append(task)
    data=b''.join(canonical_json(to_dict(t))+b'\n' for t in tasks)
    (root/'bench/public/replacement-pilot.jsonl').write_bytes(data)
    write_json_atomic(root/'bench/public/replacement-pilot-manifest.json',{
        'revision':'interface-v1','task_sha256':sha256_bytes(data),'root_groups':6,'episodes':24,
        'private_hashes':private_hashes,'constructor_sha256':sha256_bytes(Path(__file__).read_bytes()),
        'scope':'One permitted fresh pilot; six originating algorithms, four clustered semantic variants each. No model outcomes used.'})


if __name__=='__main__':main()
