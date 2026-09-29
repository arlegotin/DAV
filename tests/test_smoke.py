from pathlib import Path
import pytest


def api():
    from depverify.smoke import forecast_stage, smoke_local, memory_check
    return forecast_stage, smoke_local, memory_check


def test_forecast_includes_startup_eager_work_and_margin():
    forecast, _, _ = api()
    measurement = {'startup_seconds': 10, 'prompt_seconds_per_token': .001,
                   'generation_seconds_per_token': .02, 'call_overhead_seconds': .1,
                   'execution_seconds': .5, 'timeout_rate': 0}
    counts = {'proposals': 24, 'reviews': 72, 'eager_proposals': 8, 'candidate_invocations': 64}
    result = forecast(measurement, counts)
    expected = 10 + 104 * (3072 * .001 + .1) + (32*512 + 72*128)*.02
    assert result['model_seconds_with_margin'] == pytest.approx(expected * 1.5)
    assert result['execution_seconds_with_margin'] == 48
    assert result['generated_token_ceiling'] == 25600
    assert result['fits_model_budget']


def test_forecast_refuses_unknown_speed_and_infeasible_budget():
    forecast, _, _ = api()
    with pytest.raises(ValueError):
        forecast({}, {'proposals': 24})
    result = forecast({'startup_seconds': 100, 'prompt_seconds_per_token': 1,
                       'generation_seconds_per_token': 1, 'call_overhead_seconds': 0,
                       'execution_seconds': 1, 'timeout_rate': 0},
                      {'proposals': 24, 'reviews': 72, 'eager_proposals': 8, 'candidate_invocations': 64})
    assert not result['fits_model_budget']


def test_missing_m0_gate_stops_smoke_before_model_or_execution(tmp_path):
    _, smoke, _ = api()
    with pytest.raises(ValueError, match='gate'):
        smoke(tmp_path / 'm1', Path('config.toml'))
    assert not (tmp_path / 'work-budget.jsonl').exists()


def test_existing_swap_is_not_experiment_growth_but_sustained_growth_blocks():
    _, _, check = api()
    stable = [{'elapsed_seconds': n, 'swap_used_bytes': 20*1024**3, 'pressure_level': 1} for n in range(31)]
    assert check(stable, 36*1024**3, 6*1024**3, 8*1024**3)['passed']
    growing = [row | {'swap_used_bytes': row['swap_used_bytes'] + 1024**3} for row in stable]
    assert not check(growing, 36*1024**3, 6*1024**3, 8*1024**3, baseline_swap=20*1024**3)['passed']


def test_measured_worker_rss_counts_even_when_mlx_allocation_is_smaller():
    _,_,check=api()
    samples=[{'elapsed_seconds':0,'swap_used_bytes':0,'pressure_level':1,'worker_rss_bytes':20*1024**3}]
    assert not check(samples,36*1024**3,5*1024**3,8*1024**3)['passed']
