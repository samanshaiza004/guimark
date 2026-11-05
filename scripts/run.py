#!/usr/bin/env python3
"""Run Guimark adapters in alternating fresh processes and save raw JSON."""

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "workloads" / "manifest.json").read_text())
DEPENDENCIES = json.loads((ROOT / "dependencies.lock.json").read_text())
WORKLOADS = [item["id"] for item in MANIFEST["workloads"] if item["status"] == "implemented"]


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


def checksums(workload):
    count = MANIFEST["logical_items"]
    swap = workload == "tree.reorder.swap_adjacent.10000"
    changed = set()
    if workload == "tree.update.one.10000":
        changed.add(5000)
    elif workload == "tree.update.ten_percent.10000":
        changed.update(range(0, count, 10))
    order_hash = 0xcbf29ce484222325
    content_hash = order_hash
    prime = 0x100000001b3
    mask = (1 << 64) - 1
    for position in range(count):
        item = position
        if swap and position == 0:
            item = 1
        elif swap and position == 1:
            item = 0
        order_hash = ((order_hash ^ item) * prime) & mask
        final_byte = ord("X") if item in changed else ord("0") + item % 10
        content_hash = ((content_hash ^ item) * prime) & mask
        content_hash = ((content_hash ^ final_byte) * prime) & mask
    return f"{order_hash:016x}", f"{content_hash:016x}"


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
    required_fields = {
        "schema_version", "framework", "framework_version", "workload_id",
        "elapsed_ns", "logical_items", "changed_items", "retained_row_nodes",
        "order_checksum", "content_checksum", "diagnostics",
    }
    if set(result) != required_fields or result.get("schema_version") != 1 or result.get("framework") != framework:
        raise RuntimeError(f"invalid adapter result from {framework}: {result}")
    if not isinstance(result.get("diagnostics"), dict) or not isinstance(result.get("elapsed_ns"), int):
        raise RuntimeError(f"invalid result field types from {framework}: {result}")
    if result.get("workload_id") != workload or result.get("logical_items") != MANIFEST["logical_items"]:
        raise RuntimeError(f"workload contract mismatch from {framework}: {result}")
    expected_changed = next(item["changed_items"] for item in MANIFEST["workloads"] if item["id"] == workload)
    if result.get("changed_items") != expected_changed:
        raise RuntimeError(f"changed-item count mismatch from {framework}: {result}")
    expected_order, expected_content = checksums(workload)
    if result.get("order_checksum") != expected_order or result.get("content_checksum") != expected_content:
        raise RuntimeError(f"row order/content checksum mismatch from {framework}: {result}")
    return {"launch_wall_ns": launch_wall_ns, "adapter": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alicorn-bin", required=True, type=Path)
    parser.add_argument("--imgui-bin", required=True, type=Path)
    parser.add_argument("--alicorn-root", type=Path, default=os.environ.get("ALICORN_ROOT"))
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    binaries = {"alicorn": args.alicorn_bin.resolve(), "dear-imgui": args.imgui_bin.resolve()}
    for framework, binary in binaries.items():
        if not binary.is_file():
            parser.error(f"{framework} binary does not exist: {binary}")

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or ROOT / "results" / f"{timestamp}-{platform.machine().lower()}"
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    builds = {
        framework: {"binary_sha256": sha256(binary), "path_name": binary.name}
        for framework, binary in binaries.items()
    }
    builds["alicorn"]["source"] = revision(args.alicorn_root) if args.alicorn_root else None
    builds["dear-imgui"]["source"] = revision(ROOT / "implementations" / "dear-imgui" / "third_party" / "imgui")
    builds["guimark"] = revision(ROOT)
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
        for workload in WORKLOADS:
            order = list(binaries.items())
            if (run_index + WORKLOADS.index(workload)) % 2:
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

    capture = {
        "guimark_schema_version": 1,
        "suite": MANIFEST["suite"],
        "guimark_revision": builds["guimark"],
        "environment": environment,
        "builds": builds,
        "workload_manifest": "workloads/manifest.json",
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
    (output / "capture.json").write_text(json.dumps(capture, indent=2) + "\n")
    with (output / "capture.jsonl").open("w") as stream:
        for sample in samples:
            stream.write(json.dumps(sample, separators=(",", ":")) + "\n")
    print(f"capture: {output / 'capture.json'}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        print(f"guimark: {error}", file=sys.stderr)
        raise SystemExit(1)
