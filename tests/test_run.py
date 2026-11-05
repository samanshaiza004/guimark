import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("guimark_run", ROOT / "scripts" / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


class WorkloadContractTests(unittest.TestCase):
    def test_visible_and_offscreen_single_row_cases_are_distinct(self):
        visible = run.WORKLOAD_BY_ID["tree.update.one.visible.10000"]
        offscreen = run.WORKLOAD_BY_ID["tree.update.one.offscreen.10000"]
        self.assertEqual(visible["target_item"], 10)
        self.assertEqual(offscreen["target_item"], 5000)
        self.assertEqual(visible["changed_items"], offscreen["changed_items"])

    def test_content_checksum_covers_interior_label_bytes(self):
        self.assertNotEqual(run.fnv_text_rows(["Row 01234"]), run.fnv_text_rows(["Row 91234"]))

    def test_expected_content_differs_for_visible_and_offscreen_updates(self):
        _, baseline = run.expected_rows("tree.construct.10000")
        _, visible = run.expected_rows("tree.update.one.visible.10000")
        _, offscreen = run.expected_rows("tree.update.one.offscreen.10000")
        self.assertNotEqual(run.fnv_text_rows(baseline), run.fnv_text_rows(visible))
        self.assertNotEqual(run.fnv_text_rows(baseline), run.fnv_text_rows(offscreen))
        self.assertEqual(visible[0], baseline[0])
        self.assertNotEqual(visible[10], baseline[10])
        self.assertEqual(offscreen[10], baseline[10])
        self.assertNotEqual(offscreen[5000], baseline[5000])


class AdapterSchemaTests(unittest.TestCase):
    def valid_result(self):
        return {
            "schema_version": 1,
            "framework": "alicorn",
            "framework_version": "test",
            "workload_id": "tree.construct.10000",
            "elapsed_ns": 123,
            "logical_items": 10000,
            "changed_items": 0,
            "order_checksum": "0123456789abcdef",
            "output_validation": {
                "submitted_rows": 10000,
                "visible_rows": 45,
                "content_checksum": "0123456789abcdef",
                "rendered_output_checksum": "0123456789abcdef",
                "baseline_rendered_output_checksum": None,
                "rendered_output_kind": "alicorn-text-paint-display-list",
            },
            "diagnostics": {"layout_nodes_visited": 10000},
        }

    def test_schema_accepts_framework_specific_retained_count_as_optional(self):
        result = self.valid_result()
        self.assertEqual(run.schema_errors(result, run.SCHEMA), [])
        result["retained_row_nodes"] = 10000
        self.assertEqual(run.schema_errors(result, run.SCHEMA), [])

    def test_schema_rejects_missing_output_checksum_and_unknown_fields(self):
        result = self.valid_result()
        del result["output_validation"]["content_checksum"]
        self.assertTrue(run.schema_errors(result, run.SCHEMA))
        result = self.valid_result()
        result["unexpected"] = True
        self.assertTrue(run.schema_errors(result, run.SCHEMA))

    def test_schema_rejects_boolean_schema_version(self):
        result = self.valid_result()
        result["schema_version"] = True
        self.assertTrue(run.schema_errors(result, run.SCHEMA))

    def test_schema_evaluator_fails_closed_on_unknown_keywords(self):
        self.assertTrue(run.schema_errors("abc", {"type": "string", "minLength": 1}))

    def test_schema_file_is_the_runner_schema(self):
        self.assertEqual(
            run.SCHEMA,
            json.loads((ROOT / "schema" / "adapter-result.schema.json").read_text()),
        )


if __name__ == "__main__":
    unittest.main()
