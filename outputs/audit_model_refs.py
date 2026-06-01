"""Audit ORM model attribute references — catch wrong field names at lint time.

Per CLAUDE.md NC-DEV-001 — many recurring bugs are caused by accessing
attributes that don't exist on models (eg ClientKpiAssessment.is_submitted
instead of submitted_at).

Usage:
    cd backend
    python3 ../outputs/audit_model_refs.py

Scans all backend modules for `Model.attr` references and verifies attr exists
in the model's AST definition. Reports false negatives possible (some attrs
defined via mixins or @declared_attr) — treat output as warning, not blocker.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).parent.parent / "backend"

# Model files to harvest field names from
MODEL_FILES = [
    "app/organization/models.py",
    "app/outsource/models.py",
    "app/payroll/models.py",
    "app/project/models.py",
    "app/identity/models.py",
    "app/notification/models.py",
    "app/finance/models.py",
    "app/hiring/models.py",
    "app/onboarding/models.py",
    "app/separation/models.py",
    "app/assessment/models.py",
    "app/sales/models.py",
]

# Modules to scan for Model.attr usage
SCAN_GLOBS = [
    "app/**/router.py",
    "app/**/service.py",
    "app/**/admin_router.py",
    "app/notification/alert_rules.py",
    "app/notification/templates.py",
    "app/notification/approver_chain.py",
]

# Attributes we don't audit (SQLAlchemy / mixin / generic)
SKIP_ATTRS = {
    "is_",
    "in_",
    "isnot",
    "id",
    "created_at",
    "updated_at",
    "deleted_at",
    "model_validate",
    "model_dump",
    "metadata",
    "__tablename__",
    "__table_args__",
    "contains",
    "any",
    "has",
    "label",
    "asc",
    "desc",
    "between",
    "ilike",
    "like",
}


def collect_model_fields() -> dict[str, set[str]]:
    fields: dict[str, set[str]] = {}
    for rel in MODEL_FILES:
        path = BACKEND / rel
        if not path.exists():
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                f = set()
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        f.add(item.target.id)
                    elif isinstance(item, ast.Assign):
                        for t in item.targets:
                            if isinstance(t, ast.Name):
                                f.add(t.id)
                fields[node.name] = f
    return fields


def scan_attr_refs() -> dict[Path, set[tuple[str, str]]]:
    """Return file → set of (Model, attr) references."""
    pattern = re.compile(r"\b([A-Z][a-zA-Z]+)\.([a-z_][a-zA-Z_0-9]*)")
    by_file: dict[Path, set[tuple[str, str]]] = {}
    for glob in SCAN_GLOBS:
        for f in BACKEND.glob(glob):
            text = f.read_text()
            refs = set(pattern.findall(text))
            by_file[f] = refs
    return by_file


def main() -> int:
    models = collect_model_fields()
    by_file = scan_attr_refs()
    issues: list[str] = []

    for f, refs in sorted(by_file.items()):
        for model, attr in sorted(refs):
            if model not in models:
                continue  # Not a tracked model
            if attr in SKIP_ATTRS:
                continue
            if attr in models[model]:
                continue
            rel = f.relative_to(BACKEND)
            issues.append(f"❌ {rel}: {model}.{attr} — model fields: {sorted(models[model])[:10]}...")

    print(f"Models scanned: {len(models)}")
    print(f"Files scanned: {len(by_file)}")
    if issues:
        print(f"\n🔴 {len(issues)} potential attribute mismatches:")
        for i in issues[:30]:
            print(f"  {i}")
        if len(issues) > 30:
            print(f"  ... and {len(issues) - 30} more")
        return 1
    print("\n✅ All model attribute references match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
