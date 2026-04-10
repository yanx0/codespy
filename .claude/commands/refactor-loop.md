# Refactor Loop

Scanner-driven refactoring verification. Finds the highest-priority code target,
proposes a concrete refactoring, and re-scans to verify improvement.

## Usage

```
/refactor-loop <path>
```

`<path>` is the directory or file to scan (default: `.` if omitted).

---

## Workflow — follow these steps exactly

### Step 1 — Find the target

Run:
```bash
python3 -m codespy.cli target <path>
```

Parse the JSON output. Extract:
- `file` — the target file path
- `function` — the function to refactor (may be null for non-Python)
- `function_cc` — current cyclomatic complexity
- `action` — what to do
- `success_signal` — what a passing re-scan looks like

Show the user a one-line summary:
```
Target: `<function>` in `<file>` — CC=<N> [<RISK_LABEL>]
Action: <action>
```

### Step 2 — Read the target

Read the full target file. Identify the exact function body named in `function`.
If `function` is null (non-Python file), focus on the worst smell from `top_smells`.

### Step 3 — Propose the refactoring

Propose a concrete refactoring. Rules:
- Extract distinct logical steps into named helper functions
- Use early returns to flatten nesting (guard clauses before the main logic)
- Each extracted helper should have a single purpose and a descriptive name
- Do NOT change the public signature of the target function unless the user agrees
- Do NOT touch test files

Show the before/after as a unified diff or side-by-side. Be specific — no vague "improve this function" suggestions.

Ask: **"Apply this refactoring? (yes / no / show alternative)"**

### Step 4 — Apply if approved

If the user says yes: apply the edit with the Edit tool.
If no: propose an alternative approach (different split, different extract pattern).
If "show alternative": offer a second refactoring strategy.

Maximum 3 attempts before stopping and reporting: "Could not find an approach you want to apply — the target remains at CC=<N>."

### Step 5 — Re-scan to verify

After applying, re-scan the target file only:
```bash
python3 -m codespy.cli target <file>
```

Compare `function_cc` before and after.

Report the result:
```
Before: <function> CC=<before>  complexity_score=<before_score>
After:  <function> CC=<after>   complexity_score=<after_score>

✓ VERIFIED — complexity dropped by <delta> points
```
or:
```
✗ NOT VERIFIED — complexity is <after>, was <before>. Suggest reverting or trying a different split.
```

### Step 6 — Offer to continue

If verified: "Target is now clean. Run /refactor-loop <path> again to find the next highest-priority target."
If not verified: "Recommend reverting the change and trying a different approach."

---

## Success signal

**The refactor is verified when:**
- `function_cc` drops by ≥ 2 points, OR
- `function_cc` falls below 10

This is the named signal. Watch it, not the code.

---

## Ground rules for this workflow

1. Always show the diff before applying — never edit silently
2. Always re-scan after applying — the scanner is the proof
3. If the scanner score does not improve, say so honestly
4. Do not refactor more than one function per loop iteration
5. Stop after 3 unsuccessful attempts — reset context rather than retry blindly
6. Keep the function's external behaviour identical (same inputs, same outputs)
