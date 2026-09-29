from pathlib import Path
import pytest
from depverify.records import read_json, sha256_bytes, write_json_atomic
from depverify.tasks import load_pilot

IMAGE='python@sha256:'+'a'*64


def fixture(tmp_path):
    from depverify.smoke import prerequisite_bindings, REQUIRED_FIXTURES
    folder=tmp_path/'runner-fixtures';folder.mkdir()
    xml=folder/'results.xml'
    xml.write_text('<testsuites><testsuite>'+''.join(f'<testcase name="{name}"/>' for name in REQUIRED_FIXTURES)+'</testsuite></testsuites>')
    write_json_atomic(folder/'proof.json',{'bindings':prerequisite_bindings(IMAGE),'xml_sha256':sha256_bytes(xml.read_bytes())})
    admission=tmp_path/'pilot-admission';admission.mkdir()
    write_json_atomic(admission/'results.json',{'passed':True,'bindings':prerequisite_bindings(IMAGE),
                      'tasks':[{'episode_id':t.episode_id,'passed':True} for t in load_pilot()]})
    write_json_atomic(tmp_path/'runner-environment.json',{'image':IMAGE})
    return xml


def test_empty_or_missing_hostile_fixture_evidence_is_rejected(tmp_path):
    from depverify.smoke import validate_prerequisites
    xml=fixture(tmp_path)
    xml.write_text('<testsuites/>')
    proof=read_json(tmp_path/'runner-fixtures/proof.json');proof['xml_sha256']=sha256_bytes(xml.read_bytes())
    write_json_atomic(tmp_path/'runner-fixtures/proof.json',proof)
    with pytest.raises(ValueError,match='fixture'):validate_prerequisites(tmp_path)


def test_missing_admission_task_is_rejected(tmp_path):
    from depverify.smoke import validate_prerequisites
    fixture(tmp_path)
    p=tmp_path/'pilot-admission/results.json';data=read_json(p);data['tasks'].pop();write_json_atomic(p,data)
    with pytest.raises(ValueError,match='admission'):validate_prerequisites(tmp_path)


def test_old_image_driver_or_benchmark_binding_cannot_authorize_smoke(tmp_path):
    from depverify.smoke import validate_prerequisites
    fixture(tmp_path)
    p=tmp_path/'runner-fixtures/proof.json';proof=read_json(p);proof['bindings']['code']='0'*64;write_json_atomic(p,proof)
    with pytest.raises(ValueError,match='binding'):validate_prerequisites(tmp_path)


def test_complete_bound_prerequisites_are_accepted(tmp_path):
    from depverify.smoke import validate_prerequisites
    fixture(tmp_path)
    assert validate_prerequisites(tmp_path)['passed']
