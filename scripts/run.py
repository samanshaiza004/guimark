#!/usr/bin/env python3
"""Run Guimark adapters in alternating fresh processes and save raw JSON."""

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "workloads" / "manifest.json").read_text())
SCHEMA = json.loads((ROOT / "schema" / "adapter-result.schema.json").read_text())
DEPENDENCIES = json.loads((ROOT / "dependencies.lock.json").read_text())
WORKLOADS = [item["id"] for item in MANIFEST["workloads"] if item["status"] == "implemented"]
WORKLOAD_BY_ID = {item["id"]: item for item in MANIFEST["workloads"]}
MASK64 = (1 << 64) - 1
FNV_OFFSET = 0xcbf29ce484222325
FNV_PRIME = 0x100000001b3


def revision(path):
    try:
        commit = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
        status = subprocess.check_output(["git", "-C", str(path), "status", "--porcelain"], text=True)
        return {"commit": commit, "dirty": bool(status.strip())}
    except (OSError, subprocess.CalledProcessError):
        return None


def tool_version(command):
    if not command:
        return None
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        output = (result.stdout or result.stderr).strip().splitlines()
        return output[0] if output else None
    except OSError:
        return None


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fnv_text_rows(labels):
    """Hash full UTF-8 row labels, separated by 0xff, in display order."""
    digest = FNV_OFFSET
    for label in labels:
        for byte in label.encode("utf-8"):
            digest = ((digest ^ byte) * FNV_PRIME) & MASK64
        digest = ((digest ^ 0xff) * FNV_PRIME) & MASK64
    return f"{digest:016x}"


def fnv_order(items):
    digest = FNV_OFFSET
    for item in items:
        digest = ((digest ^ item) * FNV_PRIME) & MASK64
    return f"{digest:016x}"


def expected_rows(workload_id):
    count = MANIFEST["logical_items"]
    spec = WORKLOAD_BY_ID[workload_id]
    order = list(range(count))
    if spec["operation"] == "swap_adjacent":
        order[0], order[1] = order[1], order[0]
    changed = set()
    if spec["operation"] == "update_one":
        changed.add(spec["target_item"])
    elif spec["operation"] == "update_every_tenth":
        changed.update(range(0, count, spec["changed_every"]))
    labels = [f"Row {item // 10:04d}X" if item in changed else f"Row {item:05d}" for item in order]
    return order, labels


def _schema_type_matches(value, expected):
    kinds = expected if isinstance(expected, list) else [expected]
    for kind in kinds:
        if kind == "object" and isinstance(value, dict): return True
        if kind == "array" and isinstance(value, list): return True
        if kind == "string" and isinstance(value, str): return True
        if kind == "integer" and isinstance(value, int) and not isinstance(value, bool): return True
        if kind == "number" and isinstance(value, (int, float)) and not isinstance(value, bool): return True
        if kind == "boolean" and isinstance(value, bool): return True
        if kind == "null" and value is None: return True
    return False


def schema_errors(value, schema, path="$", errors=None):
    """Evaluate the JSON Schema keywords used by the checked-in result schema."""
    if errors is None:
        errors = []
    supported = {
        "$schema", "$id", "title", "type", "required", "properties",
        "const", "enum", "minimum", "pattern", "additionalProperties",
    }
    unknown = set(schema) - supported
    if unknown:
        errors.append(f"{path}: unsupported schema keyword(s) {sorted(unknown)!r}")
    expected_type = schema.get("type")
    if expected_type is not None and not _schema_type_matches(value, expected_type):
        errors.append(f"{path}: expected type {expected_type}")
        return errors
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in value:
                schema_errors(value[key], child_schema, f"{path}.{key}", errors)
        additional = schema.get("additionalProperties", True)
        extras = set(value) - set(properties)
        if additional is False:
            for key in sorted(extras):
                errors.append(f"{path}: unexpected property {key!r}")
        elif isinstance(additional, dict):
            for key in extras:
                schema_errors(value[key], additional, f"{path}.{key}", errors)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: value is below minimum {schema['minimum']}")
    if isinstance(value, str) and "pattern" in schema:
        if re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: value does not match {schema['pattern']!r}")
    return errors


def validate_result_schema(result):
    errors = schema_errors(result, SCHEMA)
    if errors:
        raise RuntimeError("adapter result does not match schema/adapter-result.schema.json: " + "; ".join(errors))


def run_one(framework, binary, workload):
    env = os.environ.copy()
    env["GUIMARK_FONT"] = str(ROOT / "assets" / "fonts" / "AtkinsonHyperlegibleNext-Variable.ttf")
    start = time.perf_counter_ns()
    completed = subprocess.run(
        [str(binary), workload], capture_output=True, text=True, check=False, env=env
    )
    launch_wall_ns = time.perf_counter_ns() - start
    if completed.returncode != 0:
        raise RuntimeError(
            f"{framework} failed for {workload} (exit {completed.returncode}):\n"
            f"{completed.stderr}{completed.stdout}"
        )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError(f"{framework} emitted {len(lines)} nonempty stdout lines for {workload}")
    result = json.loads(lines[0])
    validate_result_schema(result)
    if result.get("framework") != framework or result.get("workload_id") != workload:
        raise RuntimeError(f"framework/workload mismatch from {framework}: {result}")
    if result.get("logical_items") != MANIFEST["logical_items"]:
        raise RuntimeError(f"logical item count mismatch from {framework}: {result}")
    expected_changed = WORKLOAD_BY_ID[workload]["changed_items"]
    if result.get("changed_items") != expected_changed:
        raise RuntimeError(f"changed-item count mismatch from {framework}: {result}")

    order, labels = expected_rows(workload)
    expected_order = fnv_order(order)
    expected_content = fnv_text_rows(labels)
    output = result["output_validation"]
    expected_output_kind = {
        "alicorn": "alicorn-text-paint-display-list",
        "dear-imgui": "dear-imgui-draw-data",
    }[framework]
    if output["rendered_output_kind"] != expected_output_kind:
        raise RuntimeError(f"{framework} reported the wrong rendered-output kind: {result}")
    if "retained_row_nodes" in result and result["retained_row_nodes"] != len(order):
        raise RuntimeError(f"{framework} retained-row diagnostic does not match the row count: {result}")
    if output["submitted_rows"] != len(order):
        raise RuntimeError(f"{framework} submitted {output['submitted_rows']} rows, expected {len(order)}")
    if output["visible_rows"] != MANIFEST["row_geometry"]["visible_rows"]:
        raise RuntimeError(
            f"{framework} emitted {output['visible_rows']} visible text rows; expected "
            f"{MANIFEST['row_geometry']['visible_rows']}"
        )
    if result["order_checksum"] != expected_order:
        raise RuntimeError(f"{framework} row order/identity checksum mismatch: {result}")
    if output["content_checksum"] != expected_content:
        raise RuntimeError(f"{framework} full-text checksum mismatch: {result}")
    if output["rendered_output_checksum"] == f"{FNV_OFFSET:016x}":
        raise RuntimeError(f"{framework} rendered output checksum is empty: {result}")

    baseline = output["baseline_rendered_output_checksum"]
    expects_baseline = WORKLOAD_BY_ID[workload]["operation"] != "construct"
    if expects_baseline != (baseline is not None):
        raise RuntimeError(f"{framework} baseline output checksum presence mismatch: {result}")
    if expects_baseline:
        changed_output_expected = workload != "tree.update.one.offscreen.10000"
        actually_changed = baseline != output["rendered_output_checksum"]
        if actually_changed != changed_output_expected:
            raise RuntimeError(f"{framework} visible/offscreen output invariant failed: {result}")
    return {"launch_wall_ns": launch_wall_ns, "adapter": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alicorn-bin", required=True, type=Path)
    parser.add_argument("--imgui-bin", required=True, type=Path)
    parser.add_argument("--alicorn-root", type=Path, default=os.environ.get("ALICORN_ROOT"))
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--workloads", nargs="+", choices=WORKLOADS, default=WORKLOADS)
    parser.add_argument("--allow-dirty", action="store_true", help="allow dirty source trees for an experimental capture")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    if args.alicorn_root is None:
        parser.error("--alicorn-root or ALICORN_ROOT is required so the source revision can be recorded")
    args.alicorn_root = args.alicorn_root.resolve()
    if not args.alicorn_root.is_dir():
        parser.error(f"Alicorn checkout does not exist: {args.alicorn_root}")

    binaries = {"alicorn": args.alicorn_bin.resolve(), "dear-imgui": args.imgui_bin.resolve()}
    for framework, binary in binaries.items():
        if not binary.is_file():
            parser.error(f"{framework} binary does not exist: {binary}")

    builds = {
        framework: {"binary_sha256": sha256(binary), "path_name": binary.name}
        for framework, binary in binaries.items()
    }
    builds["alicorn"]["source"] = revision(args.alicorn_root)
    builds["dear-imgui"]["source"] = revision(ROOT / "implementations" / "dear-imgui" / "third_party" / "imgui")
    builds["guimark"] = {"source": revision(ROOT)}
    if not all(builds[name].get("source") for name in ("alicorn", "dear-imgui", "guimark")):
        parser.error("Guimark, Alicorn, and Dear ImGui must each be Git checkouts for a capture")
    dirty_sources = [name for name in ("alicorn", "dear-imgui", "guimark") if builds[name]["source"]["dirty"]]
    if dirty_sources and not args.allow_dirty:
        parser.error("dirty source checkout(s): " + ", ".join(dirty_sources) + "; commit sources or pass --allow-dirty for an experimental capture")

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output or ROOT / "results" / f"{timestamp}-{platform.machine().lower()}"
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    odin_name = os.environ.get("ODIN", "odin")
    odin_path = shutil.which(odin_name) or (odin_name if Path(odin_name).is_file() else None)
    cxx_command = shlex.split(os.environ.get("CXX", "c++"))
    cxx_path = shutil.which(cxx_command[0]) if cxx_command else None
    if cxx_path and cxx_command:
        cxx_command[0] = cxx_path
    environment = {
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "os": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "odin_version": tool_version([odin_path, "version"]) if odin_path else None,
        "cxx_version": tool_version(cxx_command + ["--version"]) if cxx_command else None,
    }

    samples = []
    for run_index in range(args.runs):
        for workload_index, workload in enumerate(args.workloads):
            order = list(binaries.items())
            if (run_index + workload_index) % 2:
                order.reverse()
            for framework, binary in order:
                print(f"run={run_index + 1}/{args.runs} framework={framework} workload={workload}", flush=True)
                sample = run_one(framework, binary, workload)
                samples.append({
                    "run_index": run_index + 1,
                    "framework": framework,
                    "workload_id": workload,
                    **sample,
                })

    font_path = ROOT / "assets" / "fonts" / "AtkinsonHyperlegibleNext-Variable.ttf"
    capture = {
        "guimark_schema_version": 1,
        "suite": MANIFEST["suite"],
        "guimark_revision": builds["guimark"]["source"],
        "environment": environment,
        "builds": builds,
        "dirty_source_override": bool(dirty_sources and args.allow_dirty),
        "workload_manifest": "workloads/manifest.json",
        "workload_manifest_sha256": hashlib.sha256((ROOT / "workloads" / "manifest.json").read_bytes()).hexdigest(),
        "geometry": {"viewport": MANIFEST["viewport"], "row_geometry": MANIFEST["row_geometry"]},
        "font_asset": {"path": "assets/fonts/AtkinsonHyperlegibleNext-Variable.ttf", "sha256": sha256(font_path)},
        "measurement_boundaries": {
            "alicorn": "invalidate_root through end_frame",
            "dear-imgui": "NewFrame through Render",
        },
        "build_configuration": {
            "alicorn": {"optimization": "-o:speed"},
            "dear-imgui": {
                "optimization": os.environ.get("CXXFLAGS", "-O3 -DNDEBUG -std=c++17"),
                "cxx": os.environ.get("CXX", "c++"),
                "imgui_tag": DEPENDENCIES["dear-imgui"]["tag"],
                "imgui_pinned_commit": DEPENDENCIES["dear-imgui"]["commit"],
            },
        },
        "samples": samples,
    }
    (output_dir / "capture.json").write_text(json.dumps(capture, indent=2) + "\n")
    with (output_dir / "capture.jsonl").open("w") as stream:
        for sample in samples:
            stream.write(json.dumps(sample, separators=(",", ":")) + "\n")
    print(f"capture: {output_dir / 'capture.json'}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        print(f"guimark: {error}", file=sys.stderr)
        raise SystemExit(1)
