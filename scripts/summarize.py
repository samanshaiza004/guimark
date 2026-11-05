#!/usr/bin/env python3
"""Print medians and observed ranges from a Guimark capture."""

import argparse
import json
import statistics
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="capture.json from scripts/run.py")
    args = parser.parse_args()
    capture = json.loads(args.capture.read_text())
    frameworks = sorted({sample["framework"] for sample in capture["samples"]})
    workloads = sorted({sample["workload_id"] for sample in capture["samples"]})
    print("framework\tworkload\tmedian_elapsed_ns\tmin_ns\tmax_ns\tsamples")
    for workload in workloads:
        for framework in frameworks:
            values = [
                sample["adapter"]["elapsed_ns"]
                for sample in capture["samples"]
                if sample["workload_id"] == workload and sample["framework"] == framework
            ]
            if not values:
                continue
            median = statistics.median(values)
            print(
                f"{framework}\t{workload}\t{median:g}\t"
                f"{min(values)}\t{max(values)}\t{len(values)}"
            )


if __name__ == "__main__":
    main()
