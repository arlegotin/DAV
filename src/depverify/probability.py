"""Coherent finite evidence tables and exact marginal queries."""

from collections.abc import Mapping
import os
from pathlib import Path
import tempfile

import numpy as np

from .records import CHECK_IDS, LINEAGES, VERDICTS, History, canonical_json, parse_json, read_json, write_json_atomic


class ZeroSupportError(ValueError):
    """The acquired history has no support in the declared distribution."""


def validate_joint(joint: np.ndarray) -> None:
    if not isinstance(joint, np.ndarray) or joint.shape != (2, 3, 3, 3, 3) or joint.dtype.kind not in "fiu":
        raise ValueError("joint table must be numeric with shape (2,3,3,3,3)")
    if not np.isfinite(joint).all() or np.any(joint < 0):
        raise ValueError("joint mass must be finite and nonnegative")
    if not np.isclose(joint.sum(), 1., atol=1e-12, rtol=0.):
        raise ValueError("joint table must sum to one")
    if np.any(joint[1, :, :, 1, :] != 0):
        raise ValueError("correct labels cannot coexist with genuine public FAIL")


def validate_history(history: History) -> None:
    if not isinstance(history, tuple) or len(history) != 4 or any(v is not None and v not in VERDICTS for v in history):
        raise ValueError("history requires four verdicts or None")


def _matching(joint: np.ndarray, history: History) -> np.ndarray:
    validate_history(history)
    return joint[(slice(None), *(slice(None) if v is None else VERDICTS.index(v) for v in history))]


def history_mass(joint: np.ndarray, history: History) -> float:
    validate_joint(joint)
    return float(_matching(joint, history).sum())


def posterior_correct(joint: np.ndarray, history: History) -> float:
    validate_joint(joint)
    selected = _matching(joint, history)
    mass = float(selected.sum())
    if mass <= 0.:
        raise ZeroSupportError("zero-support acquired history")
    return float(selected[1].sum() / mass)


def predictive(joint: np.ndarray, history: History, check_id: str) -> np.ndarray:
    validate_joint(joint)
    validate_history(history)
    if check_id not in CHECK_IDS:
        raise ValueError("unknown check")
    index = CHECK_IDS.index(check_id)
    if history[index] is not None:
        raise ValueError("check already acquired")
    mass = float(_matching(joint, history).sum())
    if mass <= 0.:
        raise ZeroSupportError("zero-support acquired history")
    probabilities = []
    for verdict in VERDICTS:
        branch = list(history)
        branch[index] = verdict
        probabilities.append(float(_matching(joint, tuple(branch)).sum()) / mass)
    return np.array(probabilities)


def _tables(tables: Mapping) -> dict[str, np.ndarray]:
    if not isinstance(tables, Mapping) or set(tables) != set(LINEAGES):
        raise ValueError("all three lineage tables are required")
    result = {}
    for group, values in tables.items():
        joint = np.array(values, copy=True)
        validate_joint(joint)
        joint.setflags(write=False)
        result[group] = joint
    return result


def _header(version: str) -> dict:
    if not isinstance(version, str) or not version:
        raise ValueError("table version is required")
    return {"schema_version": 1, "check_ids": list(CHECK_IDS), "verdicts": list(VERDICTS), "model_version": version}


def save_tables(path: Path, tables: Mapping, *, model_version: str) -> None:
    path = Path(path)
    validated, header = _tables(tables), _header(model_version)
    if path.suffix == ".json":
        write_json_atomic(path, header | {"tables": {g: table.tolist() for g, table in validated.items()}})
    elif path.suffix == ".npz":
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                np.savez(stream, metadata=np.array(canonical_json(header).decode("utf-8")), **validated)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    else:
        raise ValueError("probability tables must be JSON or NPZ")


def load_tables(path: Path, *, expected_version: str) -> dict[str, np.ndarray]:
    path = Path(path)
    if path.suffix == ".json":
        document = read_json(path)
        if not isinstance(document, dict) or set(document) != set(_header(expected_version)) | {"tables"}:
            raise ValueError("invalid table schema")
        header = {key: value for key, value in document.items() if key != "tables"}
        tables = document["tables"]
    elif path.suffix == ".npz":
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != {"metadata", *LINEAGES}:
                raise ValueError("invalid table archive members")
            metadata = archive["metadata"]
            if metadata.shape != () or metadata.dtype.kind not in "SU":
                raise ValueError("invalid table metadata")
            raw = metadata.item()
            header = parse_json(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            tables = {group: archive[group] for group in LINEAGES}
    else:
        raise ValueError("probability tables must be JSON or NPZ")
    if header != _header(expected_version):
        raise ValueError("table schema, check order, or model version mismatch")
    return _tables(tables)
