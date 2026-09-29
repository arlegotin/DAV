from collections import Counter
from depverify.pipeline import fake_actor_metadata
from depverify.records import Proposal, proposal_key


def api():
    from depverify import grading
    from depverify.tasks import load_pilot
    return grading, load_pilot


def make_proposal(task, status="ok"):
    body = "def solve(x): return x\n"
    return Proposal(task.episode_id, proposal_key(task, body, {"runner": "test"}, {}),
                    body, status, fake_actor_metadata(task, body), 0.)


def test_pilot_has_six_real_roots_and_semantic_contract_variants():
    _, load = api()
    tasks = load()
    assert len(tasks) == 24
    assert set(Counter(t.root_group_id for t in tasks).values()) == {4}
    assert len({t.task_class for t in tasks}) == 6
    assert len({t.episode_id for t in tasks}) == 24
    for root in {t.root_group_id for t in tasks}:
        variants = [t for t in tasks if t.root_group_id == root]
        assert len({t.contract for t in variants}) == 4
        assert all(t.split == "pilot" for t in variants)


def test_reference_and_independent_formulation_agree_before_admission():
    grading, load = api()
    for task in load():
        case = grading.private_case(task)
        assert len(case["inputs"]) >= 10
        assert case["expected"] == case["independent_expected"]
        assert len(case["mutants"]) >= 3


def test_private_expected_values_and_reference_never_enter_runner():
    grading, load = api()
    task = load()[0]
    case = grading.private_case(task)
    class Runner:
        def run(self, files, entry_point, inputs):
            assert set(files) == set(task.base_files)
            assert files[task.editable_path] == make_proposal(task).replacement
            assert inputs == case["inputs"]
            assert "reference" not in files and "expected" not in files
            return {"status": "ok", "outputs": case["expected"], "elapsed_seconds": .1}
    result = grading.grade(task, make_proposal(task), Runner())
    assert result["label"] == 1


def test_malformed_proposal_is_kept_and_not_executed():
    grading, load = api()
    task = load()[0]
    class Runner:
        def run(self, *args):
            raise AssertionError("malformed code must not be executed")
    assert grading.grade(task, make_proposal(task, "syntax_error"), Runner())["label"] == 0


def test_environment_failure_is_unresolved_and_never_guessed():
    grading, load = api()
    class Runner:
        def run(self, *args):
            return {"status": "infrastructure_error", "outputs": [], "elapsed_seconds": .1}
    task = load()[0]
    assert grading.grade(task, make_proposal(task), Runner())["label"] == "LABEL_UNRESOLVED"
