"""Fixed input-only protocol driver; executed exclusively inside the container."""

import importlib.util
import json
import sys

sys.path.insert(0, "/work")
try:
    request = json.load(sys.stdin)
    spec = importlib.util.spec_from_file_location("candidate", "/work/candidate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function = getattr(module, request["entry_point"])
    outputs = [function(value) for value in request["inputs"]]
    print(json.dumps({"status": "ok", "outputs": outputs}, allow_nan=False))
except BaseException as exc:
    print(json.dumps({"status": "candidate_failure", "outputs": [],
                      "error_type": type(exc).__name__}))
    sys.exit(1)
