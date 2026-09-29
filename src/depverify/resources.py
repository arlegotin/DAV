"""Read-only Mac diagnostics and incremental storage budgets by filesystem."""

from datetime import datetime, timezone
import math
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from .records import read_json, parse_json, write_json_atomic

GIB = 2**30


def incremental_needs(*,model_verified=False,image_verified=False):
    return {'workspace_records_and_dependencies':GIB,'model_download':0 if model_verified else 5*GIB,
            'python_image_and_download_overhead':0 if image_verified else GIB}


def _bytes(value):
    if type(value) is not int or value < 0:
        raise ValueError("storage byte measurements must be nonnegative integers")
    return value


def storage_plan(items: list[dict], *, margin: float = 1.5, reserve_bytes: int = GIB) -> dict:
    if isinstance(margin, bool) or not isinstance(margin, (float, int)) or not math.isfinite(margin) or margin < 1:
        raise ValueError("invalid storage planning margin")
    _bytes(reserve_bytes)
    volumes, reasons = {}, []
    for item in items:
        if not isinstance(item, dict) or not {"name", "path", "device", "free_bytes", "additional_bytes"}.issubset(item):
            raise ValueError("invalid storage item")
        device = str(_bytes(item["device"]))
        free = _bytes(item["free_bytes"])
        if not isinstance(item["name"], str) or not item["name"] or not isinstance(item["path"], str):
            raise ValueError("storage item requires a name and path")
        extra = item["additional_bytes"]
        if extra is None:
            reasons.append("unknown_asset_size")
            extra = 0
        else:
            _bytes(extra)
        if item.get("cached", False):
            if item.get("cache_verified") is not True:
                raise ValueError("only a complete verified cache can reduce storage needs")
            extra = 0
        volume = volumes.setdefault(device, {"free_bytes": free, "additional_bytes": 0, "items": []})
        volume["free_bytes"] = min(volume["free_bytes"], free)
        volume["additional_bytes"] += extra
        volume["items"].append(item["name"])
    if not volumes:
        raise ValueError("at least one affected filesystem is required")
    for volume in volumes.values():
        volume["required_bytes"] = math.ceil(volume["additional_bytes"] * margin) + reserve_bytes
        volume["passed"] = volume["free_bytes"] >= volume["required_bytes"]
        if not volume["passed"]:
            reasons.append("insufficient_filesystem_space")
    return {"passed": not reasons, "volumes": volumes, "reasons": sorted(set(reasons)),
            "planning_margin": margin, "reserve_bytes": reserve_bytes}


def storage_item(name: str, path: Path, additional_bytes: int | None) -> dict:
    path = Path(path).expanduser().absolute()
    existing = path
    while not existing.exists():
        if existing == existing.parent:
            raise ValueError("cannot locate storage filesystem")
        existing = existing.parent
    return {"name": name, "path": str(path), "device": existing.stat().st_dev,
            "free_bytes": shutil.disk_usage(existing).free, "additional_bytes": additional_bytes}


def model_cache_path() -> Path:
    cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    home = Path(os.environ.get("HF_HOME", str(cache / "huggingface")))
    return Path(os.environ.get("HF_HUB_CACHE", os.environ.get("HUGGINGFACE_HUB_CACHE", str(home / "hub")))).expanduser()


def _probe(command: list[str]) -> dict:
    try:
        result = subprocess.run(command, capture_output=True, text=True, shell=False, timeout=15)
        return {"command": command, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "exit_code": None, "stdout": "", "stderr": str(exc)}


def doctor_local(run_dir: Path, config_path: Path) -> dict:
    from .pipeline import REPO_ROOT, implementation_hashes, load_config
    config = load_config(config_path)
    commands = {"architecture": ["uname", "-m"], "ram": ["sysctl", "-n", "hw.memsize"],
                "chip": ["sysctl", "-n", "machdep.cpu.brand_string"], "macos": ["sw_vers"],
                "power": ["pmset", "-g", "batt"], "power_mode": ["pmset", "-g", "custom"],
                "swap": ["sysctl", "vm.swapusage"], "pressure": ["memory_pressure", "-Q"],
                "engine": ["docker", "version", "--format", "{{json .}}"]}
    probes = {name: _probe(command) for name, command in commands.items()}
    ram = int(probes["ram"]["stdout"].strip()) if probes["ram"]["exit_code"] == 0 else None
    model_verified=image_verified=False
    cache=model_cache_path()
    try:
        from .local_model import verify_assets
        identity=read_json(Path(run_dir)/'model-identity.json')
        cache=Path(identity['path'])
        verify_assets(cache,identity)
        model_verified=True
    except (OSError,ValueError,KeyError):pass
    try:
        environment=read_json(Path(run_dir)/'runner-environment.json')
        inspection=_probe(['docker','image','inspect',environment['image'],'--format','{{json .}}'])
        image=parse_json(inspection['stdout'])
        image_verified=(inspection['exit_code']==0 and image['Id']==environment['image_id'] and
                        environment['image'] in image['RepoDigests'] and image['Architecture']=='arm64' and image['Os']=='linux')
    except (OSError,ValueError,KeyError):pass
    needs=incremental_needs(model_verified=model_verified,image_verified=image_verified)
    items=[storage_item('workspace_records_and_dependencies',REPO_ROOT,needs['workspace_records_and_dependencies']),
           storage_item('model_download',cache,needs['model_download']),
           storage_item('python_image_and_download_overhead',Path.home()/'Library/Containers/com.docker.docker/Data',needs['python_image_and_download_overhead'])]
    storage = storage_plan(items, margin=config["storage"]["planning_margin"], reserve_bytes=config["storage"]["reserve_bytes"])
    passed = (all(p["exit_code"] == 0 for p in probes.values()) and probes["architecture"]["stdout"].strip() == "arm64"
              and "AC Power" in probes["power"]["stdout"] and storage["passed"])
    output = {"schema_version": 1, "recorded_at": datetime.now(timezone.utc).isoformat(), "phase": "prerequisites_only",
              "passed": passed, "status": "READY_FOR_SMOKE_SETUP" if passed else "BLOCKED", "probes": probes,
              "ram_bytes": ram, "outside_working_set_bytes": max(8 * GIB, math.ceil(.25 * ram)) if ram else None,
              "storage_items": items, "storage": storage, "storage_estimate_status": "incremental; conservative bounds for unverified assets",
              'cache_inventory':{'model_verified':model_verified,'image_verified':image_verified},
              "docker_vm_space_status": "verify separately during isolated runner setup", "artifact_hashes": implementation_hashes(config_path),
              "model_downloads": 0, "model_calls": 0, "candidate_executions": 0, "benchmark_eligible": False}
    path = Path(run_dir) / "resources" / uuid.uuid4().hex / "profile.json"
    write_json_atomic(path, output)
    write_json_atomic(Path(run_dir) / "doctor.json", output | {"profile_path": str(path)})
    return output
