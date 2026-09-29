"""M1 prerequisites, fixed smoke calls, measured forecasts, and gate evidence."""
from datetime import datetime, timezone
import math
from pathlib import Path
import re
import statistics
import subprocess
import threading
import time
import uuid
import xml.etree.ElementTree as ET

from .checks import parse_review
from .local_model import LocalModel, assemble_messages
from .pipeline import implementation_hashes, load_config, require_gate, resume_attempts, write_gate
from .records import GateResult, canonical_json, read_json, sha256_bytes, write_json_atomic
from .resources import doctor_local
from .tasks import load_pilot, materialize, preflight

REQUIRED_FIXTURES=('test_real_candidate_json_and_fresh_state','test_real_infinite_loop_is_terminated_and_removed',
                   'test_real_output_flood_is_bounded_and_removed','test_real_subprocess_spawning_is_bounded',
                   'test_real_network_access_is_denied','test_real_home_file_is_not_available',
                   'test_real_protected_file_write_is_denied')


def prerequisite_bindings(image):
    root=Path(__file__).resolve().parents[2]
    code={name:sha256_bytes((root/'src/depverify'/name).read_bytes()) for name in
          ('runner.py','_container_driver.py','tasks.py','grading.py','records.py')}
    code['test_runner.py']=sha256_bytes((root/'tests/test_runner.py').read_bytes())
    bench={file.relative_to(root).as_posix():sha256_bytes(file.read_bytes()) for file in (root/'bench').rglob('*') if file.is_file() and file.suffix in ('.py','.json','.jsonl')}
    return {'code':sha256_bytes(canonical_json(code)),'benchmark':sha256_bytes(canonical_json(bench)),
            'image':sha256_bytes(canonical_json({'image':image,'platform':'linux/arm64'}))}


def _fixture_xml(path):
    root=ET.parse(path).getroot()
    cases=list(root.iter('testcase'))
    names=[case.get('name') for case in cases]
    if not cases or not set(REQUIRED_FIXTURES).issubset(names) or any(case.find(tag) is not None for case in cases for tag in ('failure','error','skipped')):
        raise ValueError('incomplete or failed isolation fixtures')
    return cases


def validate_prerequisites(run_dir):
    run_dir=Path(run_dir)
    image=read_json(run_dir/'runner-environment.json')['image']
    bindings=prerequisite_bindings(image)
    proof=read_json(run_dir/'runner-fixtures/proof.json')
    xml=run_dir/'runner-fixtures/results.xml'
    if proof['bindings']!=bindings:raise ValueError('stale fixture bindings')
    if proof['xml_sha256']!=sha256_bytes(xml.read_bytes()):raise ValueError('fixture evidence changed')
    _fixture_xml(xml)
    admission=read_json(run_dir/'pilot-admission/results.json')
    expected={task.episode_id for task in load_pilot()}
    ids=[row['episode_id'] for row in admission['tasks']]
    if admission.get('bindings')!=bindings:raise ValueError('stale admission bindings')
    if (not admission['passed'] or len(ids)!=len(expected) or set(ids)!=expected or
            any(row['passed'] is not True for row in admission['tasks'])):
        raise ValueError('incomplete or failed pilot admission')
    return {'passed':True,'bindings':bindings}


def verify_runner_fixtures(run_dir):
    import os
    import shutil
    import sys
    run_dir=Path(run_dir)
    image=read_json(run_dir/'runner-environment.json')['image']
    before=prerequisite_bindings(image)
    folder=run_dir/'runner-fixtures'/uuid.uuid4().hex
    folder.mkdir(parents=True)
    env=os.environ | {'DEPVERIFY_DOCKER_TEST_IMAGE':image,'DEPVERIFY_RUN_DIR':str(folder/'invocations')}
    xml=folder/'results.xml'
    result=subprocess.run([sys.executable,'-m','pytest','tests/test_runner.py','-q','--junitxml='+str(xml)],
                          env=env,capture_output=True,text=True,timeout=120)
    (folder/'output.txt').write_text(result.stdout+result.stderr)
    if result.returncode or before!=prerequisite_bindings(image):raise ValueError('isolation fixture run failed or inputs changed')
    _fixture_xml(xml)
    proof={'bindings':before,'xml_sha256':sha256_bytes(xml.read_bytes()),'xml_path':str(xml)}
    write_json_atomic(folder/'proof.json',proof)
    shutil.copyfile(xml,run_dir/'runner-fixtures/results.xml')
    write_json_atomic(run_dir/'runner-fixtures/proof.json',proof)
    return proof


def forecast_stage(measurements, counts, *, margin=1.5, remaining_seconds=3600.):
    required = ('startup_seconds', 'prompt_seconds_per_token', 'generation_seconds_per_token',
                'call_overhead_seconds', 'execution_seconds', 'timeout_rate')
    if any(key not in measurements or isinstance(measurements[key], bool) or not math.isfinite(measurements[key])
           or measurements[key] < 0 for key in required):
        raise ValueError('measured runtime inputs are required')
    if measurements['generation_seconds_per_token'] == 0 or measurements['prompt_seconds_per_token'] == 0:
        raise ValueError('measured prompt and generation speeds are required')
    if set(counts) != {'proposals', 'reviews', 'eager_proposals', 'candidate_invocations'} or any(type(n) is not int or n < 0 for n in counts.values()):
        raise ValueError('all planned work counts are required')
    if margin != 1.5 or not 0 <= measurements['timeout_rate'] <= 1:
        raise ValueError('invalid planning margin or timeout frequency')
    proposals = counts['proposals'] + counts['eager_proposals']
    calls = proposals + counts['reviews']
    output = proposals * 512 + counts['reviews'] * 128
    normal = (measurements['startup_seconds'] + calls * (3072 * measurements['prompt_seconds_per_token'] + measurements['call_overhead_seconds'])
              + output * measurements['generation_seconds_per_token'])
    failed = calls * measurements['timeout_rate'] * (180 + measurements['startup_seconds'])
    model = (normal + failed) * margin
    execution = counts['candidate_invocations'] * measurements['execution_seconds'] * margin
    return {'model_seconds_with_margin': model, 'execution_seconds_with_margin': execution,
            'wall_seconds_with_margin': model + execution, 'generated_token_ceiling': output,
            'input_token_ceiling': calls * 3072, 'model_calls': calls, 'counts': counts,
            'planning_margin': margin, 'remaining_model_seconds': remaining_seconds,
            'final_call_reservation_seconds': 180., 'fits_model_budget': model + 180 <= remaining_seconds}


def memory_check(samples, ram_bytes, peak_model_bytes, engine_bytes, *, baseline_swap=None):
    if not samples:
        return {'passed': False, 'reason': 'no memory measurements'}
    reserve = max(8*1024**3, math.ceil(.25 * ram_bytes))
    planned = peak_model_bytes + engine_bytes + 512*1024**2 + 1024**3
    baseline = samples[0]['swap_used_bytes'] if baseline_swap is None else baseline_swap
    serious = any(row['pressure_level'] >= 4 for row in samples)
    warning = [row for row in samples if row['pressure_level'] >= 2]
    warning_sustained = len(warning) >= 3 and warning[-1]['elapsed_seconds'] - warning[0]['elapsed_seconds'] >= 30
    swap = [row for row in samples if row['swap_used_bytes'] - baseline >= 512*1024**2]
    growth = len(swap) >= 3 and swap[-1]['elapsed_seconds'] - swap[0]['elapsed_seconds'] >= 30
    return {'passed': planned <= ram_bytes-reserve and not serious and not warning_sustained and not growth,
            'outside_working_set_bytes': reserve, 'planned_working_set_bytes': planned,
            'baseline_swap_bytes': baseline, 'maximum_swap_bytes': max(row['swap_used_bytes'] for row in samples),
            'serious_pressure': serious, 'sustained_warning': warning_sustained, 'sustained_swap_growth': growth}


class MemoryMonitor:
    """Trusted system probes; rules are frozen in the smoke manifest before load."""
    def __init__(self):
        self.samples, self.errors = [], []
        self.stop = threading.Event()
        self.started = time.monotonic()
        self.thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self):
        while not self.stop.is_set():
            try:
                swap = subprocess.run(['sysctl', 'vm.swapusage'], capture_output=True, text=True, timeout=2, check=True)
                pressure = subprocess.run(['sysctl', '-n', 'kern.memorystatus_vm_pressure_level'],
                                          capture_output=True, text=True, timeout=2, check=True)
                match = re.search(r'used\s*=\s*([0-9.]+)([MG])', swap.stdout)
                if not match:
                    raise ValueError('unparseable swap measurement')
                self.samples.append({'elapsed_seconds': time.monotonic()-self.started,
                                     'swap_used_bytes': int(float(match[1])*1024**(2 if match[2]=='M' else 3)),
                                     'pressure_level': int(pressure.stdout.strip())})
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                self.errors.append(type(exc).__name__)
            self.stop.wait(1)

    def start(self):
        self.thread.start()
        # Obtain a baseline before model loading, not after it.
        until = time.monotonic()+5
        while not self.samples and not self.errors and time.monotonic() < until:
            time.sleep(.01)
        if not self.samples:
            raise RuntimeError('cannot measure the memory baseline')

    def close(self):
        self.stop.set()
        self.thread.join(timeout=5)


def _limits(config):
    return {'total_seconds': {'model': config['budgets']['model_total_seconds']},
            'stage_seconds': {stage: {'model': cap} for stage, cap in config['budgets']['stage_model_seconds'].items()},
            'per_call_seconds': {'model': 180., 'execution': 10.}}


def _smoke_local(run_dir, config_path):
    run_dir, config_path = Path(run_dir), Path(config_path)
    hashes = implementation_hashes(config_path)
    require_gate(run_dir.parent/'m0/gate.json', stage='M0', expected_hashes=hashes)
    config = load_config(config_path)
    profile = doctor_local(run_dir, config_path)
    if not profile['passed']:
        raise ValueError('local prerequisites are blocked')
    identity = read_json(run_dir/'model-identity.json')
    environment = read_json(run_dir/'runner-environment.json')
    validate_prerequisites(run_dir)
    admission = read_json(run_dir/'pilot-admission/results.json')
    fixtures = ET.parse(run_dir/'runner-fixtures/results.xml').getroot()
    if not admission['passed'] or any(int(suite.get('failures', '0')) or int(suite.get('errors', '0')) or
                                      int(suite.get('skipped','0')) for suite in fixtures.iter('testsuite')):
        raise ValueError('pilot admission or real isolation tests failed')
    if environment['virtual_disk_probe']['status'] != 'ok' or environment['virtual_disk_probe']['outputs'][0]['vm_free_bytes'] < 1024**3:
        raise ValueError('Docker virtual disk headroom unavailable')
    tasks = {task.episode_id: task for task in load_pilot()}
    ids = ('pilot-interval-0', 'pilot-config-0', 'pilot-parser-0')
    folder = run_dir/'smoke'/uuid.uuid4().hex
    manifest = {'task_ids': ids, 'actor_seeds': [1100, 1101, 1102], 'review_seeds': [2100, 3100, 4100],
                'warmup_seed': 1099, 'repeat': 'R1 each task once with the identical input and seed',
                'identity': identity, 'artifact_hashes': hashes, 'profile_hash': sha256_bytes(canonical_json(profile)),
                'memory_rules': {'sample_seconds': 1, 'critical_pressure_level': 4, 'warning_pressure_level': 2,
                                 'sustained_seconds': 30, 'minimum_samples': 3, 'swap_growth_bytes': 512*1024**2},
                'stage_model_budget_seconds': 900, 'next_stage_counts': {'proposals':24,'reviews':72,'eager_proposals':8,'candidate_invocations':64}}
    write_json_atomic(folder/'frozen-smoke.json', manifest)
    ledger = run_dir.parent/'work-budget.jsonl'
    model = LocalModel(Path(identity['path']), identity, ledger, _limits(config), 'M1', record_dir=folder/'model-calls')
    monitor = MemoryMonitor()
    calls, proposals, reviews, repeats = [], [], [], []
    try:
        monitor.start()
        startup = model.start()
        calls.append(model.generate(assemble_messages(tasks[ids[0]], 'proposal'), role='proposal', seed=1099, temperature=.2))
        for index, task_id in enumerate(ids):
            task = tasks[task_id]
            actor = model.generate(assemble_messages(task, 'proposal'), role='proposal', seed=1100+index, temperature=.2)
            calls.append(actor)
            root = materialize(task, folder/'disposable')
            status, preflight_seconds = preflight(task, actor['text'], root)
            proposals.append({'episode_id':task_id,'preflight_status':status, 'preflight_seconds':preflight_seconds,'output':actor})
            first = None
            for role_index, role in enumerate(('R1','R2','D')):
                seed = manifest['review_seeds'][role_index]+index
                output = model.generate(assemble_messages(task, role, actor['text']), role=role, seed=seed, temperature=0)
                calls.append(output)
                verdict, parse_status, reason = parse_review(output['text'], truncated=output['status']=='truncated')
                reviews.append({'episode_id':task_id,'check_id':role,'verdict':verdict,'status':parse_status,'reason':reason,'output':output})
                if role == 'R1':
                    first = reviews[-1]
            repeated = model.generate(assemble_messages(task,'R1',actor['text']),role='R1',seed=2100+index,temperature=0)
            calls.append(repeated)
            verdict, status, reason = parse_review(repeated['text'],truncated=repeated['status']=='truncated')
            reviews.append({'episode_id':task_id,'check_id':'R1-repeat','verdict':verdict,'status':status,'reason':reason,'output':repeated})
            repeats.append({'episode_id':task_id,'changed_text':first['output']['text'] != repeated['text'],
                            'changed_verdict':first['verdict'] != verdict})
            if not memory_check(monitor.samples,profile['ram_bytes'],max(c.get('peak_memory_bytes',0) for c in calls),
                                environment['engine_memory_bytes'])['passed']:
                raise RuntimeError('memory envelope failed; stop expansion')
    finally:
        model.close()
        monitor.close()
        write_json_atomic(folder/'partial-results.json', {'calls':calls,'proposals':proposals,'reviews':reviews,
                           'repeats':repeats,'memory_samples':monitor.samples,'memory_errors':monitor.errors})
    timed = [c for c in calls[1:] if c.get('prompt_tps',0)>0 and c.get('generation_tps',0)>0]
    if not timed:
        raise ValueError('no valid warm timing measurements')
    measurements = {'startup_seconds':startup['elapsed_seconds'],
                    'prompt_seconds_per_token':statistics.median(1/c['prompt_tps'] for c in timed),
                    'generation_seconds_per_token':statistics.median(1/c['generation_tps'] for c in timed),
                    'call_overhead_seconds':statistics.median(max(0,c['elapsed_seconds']-c['input_tokens']/c['prompt_tps']-c['output_tokens']/c['generation_tps']) for c in timed),
                    'execution_seconds':statistics.median(row['runs']['reference']['seconds'] for row in admission['tasks']),
                    'timeout_rate':sum(c['status']=='model_timeout' for c in calls)/len(calls)}
    forecast = forecast_stage(measurements, manifest['next_stage_counts'])
    valid_reviews = sum(row['status']=='ok' and row['output']['status']=='ok' for row in reviews)
    memory = memory_check(monitor.samples,profile['ram_bytes'],max(c.get('peak_memory_bytes',0) for c in calls),environment['engine_memory_bytes'])
    criteria = {'ordinary_tasks':all(p['preflight_status']=='ok' and p['output']['status']=='ok' for p in proposals),
                'isolation_fixtures':True,'pilot_admission':True,'strict_review_parsing':valid_reviews/len(reviews)>=.9,
                'model_timeout_enforced':True,'memory_envelope':memory['passed'] and not monitor.errors,
                'm2_budget':forecast['fits_model_budget'],'source_unchanged':hashes==implementation_hashes(config_path)}
    # Record role-specific caps directly from each immutable request, rather than
    # depending on schedule indices in the result list.
    roles = [read_json(folder/'model-calls'/(c['attempt_id']+'.json'))['request']['role'] for c in calls]
    criteria['token_caps'] = all(c['input_tokens']<=3072 and c['output_tokens']<=(512 if role=='proposal' else 128)
                                for c,role in zip(calls,roles))
    result = {'passed':all(criteria.values()),'criteria':criteria,'valid_reviews':valid_reviews,'reviews':len(reviews),
              'measurements':measurements,'forecast':forecast,'memory':memory,'repeat_results':repeats,
              'model_active_seconds':resume_attempts(ledger)['model_seconds'],'evidence_path':str(folder),
              'model_identity':identity,'profile':profile}
    write_json_atomic(folder/'results.json',result)
    write_json_atomic(run_dir/'smoke-results.json',result)
    write_gate(run_dir/'gate.json',GateResult('M1','GO' if result['passed'] else 'BLOCKED',datetime.now(timezone.utc).isoformat(),
        hashes | {'model':sha256_bytes(canonical_json(identity)),'environment':sha256_bytes(canonical_json(environment)),
                  'evidence':sha256_bytes(canonical_json(result))},criteria,
        ('Measured native smoke envelope; no natural benchmark claim.',), (str(folder/'results.json'),), resume_attempts(ledger)))
    return result


def smoke_local(run_dir, config_path):
    run_dir = Path(run_dir)
    # Missing/stale authorization rejects the command before any work.
    require_gate(run_dir.parent/'m0/gate.json',stage='M0',expected_hashes=implementation_hashes(config_path))
    try:
        return _smoke_local(run_dir, config_path)
    except (OSError, ValueError, RuntimeError) as exc:
        evidence = tuple(str(p) for p in (run_dir/'smoke').glob('*/partial-results.json'))
        snapshot = resume_attempts(run_dir.parent/'work-budget.jsonl')
        write_gate(run_dir/'gate.json',GateResult('M1','BLOCKED',datetime.now(timezone.utc).isoformat(),
            implementation_hashes(config_path),{'completed_smoke':False},(str(exc),),evidence,snapshot))
        return {'passed':False,'status':'BLOCKED','reason':str(exc),'partial_evidence':evidence}
