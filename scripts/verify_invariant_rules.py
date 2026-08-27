"""One-off verification of the ground_truth.invariant_rules contract.

Checks tasks/schema.json, the autobench.schema.InvariantRule Pydantic model,
and the two financial_reconciliation tasks that use invariant_rules, against
the expected rule_id / sql_assertion shape. Prints a PASS/FAIL report.

Usage: python scripts/verify_invariant_rules.py
"""

from __future__ import annotations

import importlib
import inspect
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SCHEMA_PATH = REPO_ROOT / "tasks" / "schema.json"
TASK_003_PATH = REPO_ROOT / "tasks" / "financial_reconciliation" / "task_003.json"
TASK_005_PATH = REPO_ROOT / "tasks" / "financial_reconciliation" / "task_005.json"

EXPECTED_REQUIRED = ["rule_id", "sql_assertion"]

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    line = f"[{status}] {name}"
    if not condition and detail:
        line += f" — {detail}"
    print(line)
    if not condition:
        failures.append(name)
    return condition


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    # ---- 1. tasks/schema.json shape ----
    section("1. tasks/schema.json ground_truth.invariant_rules shape")
    schema = load_json(SCHEMA_PATH)
    inv = (
        schema.get("properties", {})
        .get("ground_truth", {})
        .get("properties", {})
        .get("invariant_rules", {})
    )
    check("ground_truth.properties.invariant_rules exists", bool(inv), f"got {inv!r}")
    check("invariant_rules.type == 'array'", inv.get("type") == "array", f"got {inv.get('type')!r}")

    items = inv.get("items", {})
    check("invariant_rules.items.type == 'object'", items.get("type") == "object", f"got {items.get('type')!r}")

    required = items.get("required", [])
    check(
        f"invariant_rules.items.required == {EXPECTED_REQUIRED}",
        required == EXPECTED_REQUIRED,
        f"got {required!r}",
    )

    props = items.get("properties", {})
    check(
        "items.properties.rule_id.type == 'string'",
        props.get("rule_id", {}).get("type") == "string",
        f"got {props.get('rule_id')!r}",
    )
    check(
        "items.properties.sql_assertion.type == 'string'",
        props.get("sql_assertion", {}).get("type") == "string",
        f"got {props.get('sql_assertion')!r}",
    )

    # ---- 2. autobench/schema.py InvariantRule model ----
    section("2. autobench.schema.InvariantRule model shape")
    schema_module = importlib.import_module("autobench.schema")
    InvariantRule = getattr(schema_module, "InvariantRule", None)
    check(
        "InvariantRule class exists in autobench.schema",
        InvariantRule is not None and inspect.isclass(InvariantRule),
        f"module file: {inspect.getfile(schema_module)}",
    )

    if InvariantRule is not None:
        fields = InvariantRule.model_fields
        field_names = set(fields.keys())
        expected_fields = {"rule_id", "sql_assertion"}

        check(
            "InvariantRule has a 'rule_id: str' field",
            fields.get("rule_id") is not None and fields["rule_id"].annotation is str,
            f"got {fields.get('rule_id')!r}",
        )
        check(
            "InvariantRule has a 'sql_assertion: str' field",
            fields.get("sql_assertion") is not None and fields["sql_assertion"].annotation is str,
            f"got {fields.get('sql_assertion')!r}",
        )

        required_names = {n for n, f in fields.items() if f.is_required()}
        check(
            "InvariantRule has exactly {rule_id, sql_assertion} as required fields, no extras",
            field_names == expected_fields and required_names == expected_fields,
            f"all_fields={sorted(field_names)}, required={sorted(required_names)}",
        )
    else:
        check("InvariantRule has a 'rule_id: str' field", False, "class not found")
        check("InvariantRule has a 'sql_assertion: str' field", False, "class not found")
        check(
            "InvariantRule has exactly {rule_id, sql_assertion} as required fields, no extras",
            False,
            "class not found",
        )

    GroundTruth = getattr(schema_module, "GroundTruth", None)
    check("GroundTruth class exists in autobench.schema", GroundTruth is not None)
    if GroundTruth is not None and InvariantRule is not None:
        gt_fields = GroundTruth.model_fields
        inv_field = gt_fields.get("invariant_rules")
        expected_annotation = list[InvariantRule]
        check(
            "GroundTruth.invariant_rules is typed as list[InvariantRule]",
            inv_field is not None and inv_field.annotation == expected_annotation,
            f"got {inv_field.annotation if inv_field else None!r}, expected {expected_annotation!r}",
        )

    # ---- 3 & 4. task_003 / task_005 invariant_rules content ----
    section("3 & 4. task_003 / task_005 invariant_rules content")

    def load_invariants(path: Path) -> list[dict]:
        return load_json(path).get("ground_truth", {}).get("invariant_rules", [])

    task_003_rules = load_invariants(TASK_003_PATH)
    task_005_rules = load_invariants(TASK_005_PATH)

    check(
        f"{TASK_003_PATH.relative_to(REPO_ROOT)} ground_truth.invariant_rules is non-empty",
        len(task_003_rules) > 0,
        f"got {len(task_003_rules)} entries",
    )
    check(
        f"{TASK_005_PATH.relative_to(REPO_ROOT)} ground_truth.invariant_rules is non-empty",
        len(task_005_rules) > 0,
        f"got {len(task_005_rules)} entries",
    )

    for label, rules in (("task_003", task_003_rules), ("task_005", task_005_rules)):
        for i, rule in enumerate(rules):
            has_both = "rule_id" in rule and "sql_assertion" in rule
            check(
                f"{label} invariant_rules[{i}] has both rule_id and sql_assertion",
                has_both,
                f"keys present: {sorted(rule.keys())}",
            )

    print("\n--- task_003.json ground_truth.invariant_rules ---")
    print(json.dumps(task_003_rules, indent=2))
    print("\n--- task_005.json ground_truth.invariant_rules ---")
    print(json.dumps(task_005_rules, indent=2))

    # ---- 5. InvariantRule.model_validate round-trip ----
    section("5. InvariantRule.model_validate round-trip on task entries")
    if InvariantRule is not None:
        for label, rules in (("task_003", task_003_rules), ("task_005", task_005_rules)):
            for i, rule in enumerate(rules):
                try:
                    InvariantRule.model_validate(rule)
                    check(f"{label} invariant_rules[{i}] parses as InvariantRule", True)
                except Exception as exc:  # pydantic.ValidationError or similar
                    check(
                        f"{label} invariant_rules[{i}] parses as InvariantRule",
                        False,
                        str(exc).splitlines()[0],
                    )
    else:
        check("InvariantRule.model_validate round-trip", False, "InvariantRule class not available")

    # ---- Summary ----
    print("\n=== SUMMARY ===")
    if failures:
        print(f"FAIL — {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("PASS — all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
