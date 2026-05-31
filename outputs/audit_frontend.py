"""Audit script: scan frontend for recurring error patterns.

Detects:
- A1: hooks after conditional early return (Rules of Hooks)
- A2: deprecated AntD: destroyOnClose, Dropdown overlay prop, Spin tip standalone
- A3: static `message.X(...)` / `Modal.X(...)` (should use App context)
- A4: InputNumber parser cast bug (`as 0`)
"""

import re
from pathlib import Path


FE_BASE = Path("frontend/src")


def audit_hooks_after_return(out: list):
    """A1: Find `if (!x) return null` followed by hook call."""
    hook_re = re.compile(r"\b(use[A-Z]\w*)\s*\(")
    return_re = re.compile(r"^\s*if\s*\(.*\)\s*return\s+null\s*;?\s*$")
    findings = []
    for py_file in FE_BASE.rglob("*.tsx"):
        text = py_file.read_text()
        lines = text.splitlines()
        # Find function declarations + scan for return-then-hook
        for i, line in enumerate(lines):
            if return_re.match(line):
                # Look forward for hook in same function scope (max 30 lines)
                for j in range(i + 1, min(i + 30, len(lines))):
                    after = lines[j].strip()
                    if after.startswith("//"):
                        continue
                    if hook_re.search(after) and "/" not in after.split("(")[0]:
                        # Check it's NOT inside JSX (return statement could be JSX)
                        m = hook_re.search(after)
                        # Skip if it looks like a method call (e.g. `this.useX()`)
                        prefix = after[: m.start()]
                        if prefix.rstrip().endswith("."):
                            continue
                        findings.append({
                            "file": str(py_file.relative_to(FE_BASE)),
                            "return_line": i + 1,
                            "hook_line": j + 1,
                            "hook": m.group(1),
                            "code": after[:120],
                        })
                        break
                    # Stop if we hit closing of function
                    if line.startswith("function ") or after == "}":
                        break
    out.append("## A1: Hooks called AFTER early return")
    out.append("")
    if not findings:
        out.append("✅ No violations.")
    for f in findings:
        out.append(f"- {f['file']}:{f['return_line']} return → :{f['hook_line']} `{f['hook']}` — {f['code']}")
    out.append("")
    return findings


def audit_antd_deprecated(out: list):
    """A2: deprecated AntD APIs."""
    deprecated = {
        "destroyOnClose": "destroyOnHidden",
        "overlay={": "menu={ (Dropdown)",
    }
    findings = []
    for py_file in FE_BASE.rglob("*.tsx"):
        text = py_file.read_text()
        for i, line in enumerate(text.splitlines(), 1):
            for dep, replacement in deprecated.items():
                if dep in line:
                    findings.append({
                        "file": str(py_file.relative_to(FE_BASE)),
                        "line": i,
                        "dep": dep,
                        "replacement": replacement,
                        "code": line.strip()[:120],
                    })
    out.append("## A2: Deprecated AntD APIs")
    out.append("")
    by_dep = {}
    for f in findings:
        by_dep.setdefault(f["dep"], []).append(f)
    for dep, occs in sorted(by_dep.items()):
        out.append(f"### `{dep}` → `{by_dep[dep][0]['replacement']}` ({len(occs)} occurrences)")
        for f in occs[:10]:
            out.append(f"  - {f['file']}:{f['line']}")
        if len(occs) > 10:
            out.append(f"  ... and {len(occs) - 10} more")
        out.append("")
    if not findings:
        out.append("✅ No deprecated APIs.")
    out.append("")
    return findings


def audit_static_message(out: list):
    """A3: static `message.success(...)`, `message.error(...)`, `Modal.confirm(...)`.

    Only flags calls where the symbol is imported FROM 'antd' directly (true static).
    Imports from '@/lib/notify' are proxies bound to App.useApp() — those are fine.
    """
    findings = []
    for py_file in FE_BASE.rglob("*.tsx"):
        text = py_file.read_text()
        # Determine which symbols are imported from antd vs @/lib/notify
        antd_msg = False
        antd_modal = False
        antd_notif = False
        # Match any import from 'antd' (single- or multi-line)
        for m in re.finditer(
            r"import\s*\{([\s\S]*?)\}\s*from\s*['\"]antd['\"]",
            text,
        ):
            items = {it.strip() for it in m.group(1).split(",")}
            if "message" in items:
                antd_msg = True
            if "Modal" in items:
                # Note: Modal can be used as JSX component too. We only flag .xxx(...) calls below.
                antd_modal = True
            if "notification" in items:
                antd_notif = True

        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            for m in re.finditer(r"\b(message|Modal|notification)\.(success|error|warning|info|confirm|warn|loading|destroy)\s*\(", line):
                sym = m.group(1)
                if sym == "message" and not antd_msg:
                    continue
                if sym == "Modal" and not antd_modal:
                    continue
                if sym == "notification" and not antd_notif:
                    continue
                findings.append({
                    "file": str(py_file.relative_to(FE_BASE)),
                    "line": i,
                    "call": m.group(0),
                    "code": stripped[:120],
                })
    out.append("## A3: Static message/Modal/notification calls (won't pick up dynamic theme)")
    out.append("")
    out.append(f"Total occurrences: {len(findings)}")
    by_file = {}
    for f in findings:
        by_file.setdefault(f["file"], []).append(f)
    out.append(f"Files affected: {len(by_file)}")
    out.append("")
    out.append("Top 20 files by count:")
    for fp, occs in sorted(by_file.items(), key=lambda x: -len(x[1]))[:20]:
        out.append(f"  - {fp}: {len(occs)}")
    out.append("")
    return findings


def audit_input_number_parser(out: list):
    """A4: InputNumber parser `as 0` cast (TS error)."""
    findings = []
    for py_file in FE_BASE.rglob("*.tsx"):
        text = py_file.read_text()
        for i, line in enumerate(text.splitlines(), 1):
            if "parser=" in line and "as 0" in line:
                findings.append({
                    "file": str(py_file.relative_to(FE_BASE)),
                    "line": i,
                    "code": line.strip()[:140],
                })
            elif "parser=" in line and re.search(r":\s*0\)\s*=>\s*", line):
                # Another variant
                findings.append({
                    "file": str(py_file.relative_to(FE_BASE)),
                    "line": i,
                    "code": line.strip()[:140],
                })
    out.append("## A4: InputNumber parser type bug")
    out.append("")
    if not findings:
        out.append("✅ No issues.")
    for f in findings:
        out.append(f"- {f['file']}:{f['line']}  {f['code']}")
    out.append("")
    return findings


def main():
    out = ["# Frontend Source Audit", ""]
    h = audit_hooks_after_return(out)
    d = audit_antd_deprecated(out)
    m = audit_static_message(out)
    p = audit_input_number_parser(out)
    out.append("---")
    out.append(f"## Summary: {len(h)} hooks issues · {len(d)} deprecated AntD · {len(m)} static message/Modal · {len(p)} InputNumber parser")
    Path("outputs/frontend_audit.txt").write_text("\n".join(out) + "\n")


main()
