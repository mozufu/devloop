"""Load release-generated Zutai descriptors for host-facing record boundaries."""
import json
from pathlib import Path
from .core import Refusal


def fields(module, name, value):
    path = Path(__file__).with_name("bindings.json")
    if not path.is_file():
        raise Refusal("E_INSTALL: run tools/generate_bindings.py before packaging")
    descriptors = json.loads(path.read_text())[module][name]
    if not isinstance(value, dict):
        raise Refusal(f"E_STRUCTURE:{module}.{name}")
    required = {f["name"] for f in descriptors if not f["optional"]}
    known = {f["name"] for f in descriptors}
    if not required <= value.keys() or not value.keys() <= known:
        raise Refusal(f"E_FIELDS:{module}.{name}")
    return value
