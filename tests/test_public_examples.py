"""Public examples must work from a clone without its research run directory."""
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
