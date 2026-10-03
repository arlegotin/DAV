"""Public examples must work from a clone without its research run directory."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]


def run_example(name,*args):
    return subprocess.run([sys.executable,str(ROOT/'examples'/name),*args],
                          capture_output=True,text=True,timeout=30)


def test_copied_evidence_example_does_not_double_count_a_pass():
    result=run_example('copied_evidence.py','--json')
    assert result.returncode==0,result.stderr
    output=json.loads(result.stdout)
    assert output['one_pass']==pytest.approx(.8)
    assert output['copied_passes']==pytest.approx(.8)
    assert output['independent_passes']==pytest.approx(16/17)


def test_public_replay_reproduces_both_separate_pilots_without_native_work():
    result=run_example('replay_pilots.py','--json')
    assert result.returncode==0,result.stderr
    output=json.loads(result.stdout)
    original,replacement=output['panels']['original'],output['panels']['replacement']
    assert (original['status'],replacement['status'])==('INCONCLUSIVE','NO_GO')
    for panel,count,expected,eager in [(original,32,(3,3,18),(1,2,5)),
                                      (replacement,68,(8,0,16),(2,0,6))]:
        assert panel['verified_policies']==count
        for summary,wanted in [(panel['policies']['test_only'],expected),(panel['eager_test_only'],eager)]:
            assert tuple(summary[k] for k in ('correct_accepts','incorrect_accepts','deferrals'))==wanted
        assert panel['natural_episodes']==24 and panel['root_groups']==6
    assert replacement['policies']['test_only']['mean_loss']==pytest.approx(5.302,abs=.0005)
    assert output['replacement_test_minus_defer']['interval_95']==pytest.approx([-2.660087410440409,.26167690090625323])
    assert output['model_calls']==output['candidate_executions']==0


def test_public_replay_rejects_changed_evidence_before_scoring(tmp_path):
    destination=tmp_path/'pilots'
    shutil.copytree(ROOT/'artifacts/pilots',destination)
    path=destination/'replacement/episodes/natural/replacement-migration-0/R1.json'
    row=json.loads(path.read_text());row['verdict']='PASS';path.write_text(json.dumps(row))
    result=run_example('replay_pilots.py','--artifacts',str(destination),'--json')
    assert result.returncode==1
    assert 'checksum' in result.stderr.lower()
    assert result.stdout==''


def test_public_replay_refuses_manifest_path_traversal(tmp_path):
    destination=tmp_path/'pilots';destination.mkdir()
    manifest=json.loads((ROOT/'artifacts/pilots/manifest.json').read_text())
    manifest['files']={'../outside.json':{'sha256':'a'*64}}
    (destination/'manifest.json').write_text(json.dumps(manifest))
    result=run_example('replay_pilots.py','--artifacts',str(destination),'--verify-only')
    assert result.returncode==1
    assert 'path' in result.stderr.lower()
    assert result.stdout==''


def test_public_replay_refuses_an_empty_inventory(tmp_path):
    manifest=json.loads((ROOT/'artifacts/pilots/manifest.json').read_text());manifest['files']={}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    result=run_example('replay_pilots.py','--artifacts',str(tmp_path),'--verify-only')
    assert result.returncode==1
    assert 'inventory' in result.stderr.lower()


def test_public_replay_succeeds_when_writes_processes_and_network_are_forbidden():
    # Catch any accidental return to live ledger recovery or native execution.
    code='''
import os, runpy, sys
def forbid_side_effects(event, args):
    if event == 'open':
        _, mode, flags = args
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise RuntimeError('write forbidden by replay audit: ' + str(args[0]))
    if event in {'os.mkdir', 'os.remove', 'os.rename', 'os.rmdir', 'os.truncate', 'os.chmod',
                 'os.system', 'os.posix_spawn', 'subprocess.Popen', 'socket.connect', 'socket.bind'}:
        raise RuntimeError('side effect forbidden by replay audit: ' + event)
sys.addaudithook(forbid_side_effects)
script = sys.argv[1]
sys.argv = [script, '--json']
runpy.run_path(script, run_name='__main__')
'''
    result=subprocess.run([sys.executable,'-B','-c',code,str(ROOT/'examples/replay_pilots.py')],
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    output=json.loads(result.stdout)
    assert output['verified_files']==836
    assert output['model_calls']==output['candidate_executions']==0
    assert output['panels']['replacement']['policies']['test_only']['correct_accepts']==8


def portable_copy(tmp_path):
    destination=tmp_path/'pilots'
    shutil.copytree(ROOT/'artifacts/pilots',destination)
    # An old publication accidentally included this zero-byte side effect.
    (destination/'work-budget.jsonl.lock').unlink(missing_ok=True)
    return destination


def refresh_inventory_checksum(root,path):
    manifest_path=root/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    manifest['files'][path.relative_to(root).as_posix()]['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))


def assert_replay_rejects_without_changes(root,message):
    before={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result=run_example('replay_pilots.py','--artifacts',str(root),'--json')
    assert result.returncode==1
    assert message in result.stderr.lower()
    assert result.stdout==''
    after={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert after==before


def test_public_replay_rejects_incomplete_ledger_without_repairing_it(tmp_path):
    root=portable_copy(tmp_path);ledger=root/'work-budget.jsonl'
    with ledger.open('ab') as stream:stream.write(b'{"type":"reserve",')
    refresh_inventory_checksum(root,ledger)
    assert_replay_rejects_without_changes(root,'incomplete')


def test_public_replay_rejects_pending_execution_without_creating_a_lock(tmp_path):
    root=portable_copy(tmp_path);ledger=root/'work-budget.jsonl'
    event={'event_id':'reserve:container-public-pending','type':'reserve',
           'attempt_id':'container-public-pending','stage':'M2','work_kind':'execution',
           'allowance_seconds':10.0}
    with ledger.open('a') as stream:stream.write(json.dumps(event)+'\n')
    refresh_inventory_checksum(root,ledger)
    assert_replay_rejects_without_changes(root,'pending execution')


def test_public_replay_rejects_failed_cleanup_without_creating_a_lock(tmp_path):
    root=portable_copy(tmp_path)
    invocation=next((root/'replacement/container-calls').glob('*.json'))
    row=json.loads(invocation.read_text());row['cleanup_ok']=False
    invocation.write_text(json.dumps(row))
    refresh_inventory_checksum(root,invocation)
    assert_replay_rejects_without_changes(root,'unconfirmed container cleanup')
