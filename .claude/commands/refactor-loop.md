# Refactor Loop

Scanner-driven refactoring. Finds the highest-priority target, proposes the
smallest effective fix, and re-scans to verify improvement.

Policy: prefer the minimal option. Optimize for measurable health gain with
low behavioral risk and small change budget. See CLAUDE.md §5 for full policy.

## Usage

```
/refactor-loop <path>
```

---

## Workflow

### Step 1 — Find the target

```bash
python3 -m codespy.cli target <path>
```

Extract: `file`, `function`, `function_cc`, `top_smells`, `risk_label`.

Show the user:
```
Target:  `<function>` in `<file>` — CC=<N> [<RISK_LABEL>]
Why:     <primary smell or complexity driver from top_smells>
Signal:  CC drops ≥2 points or falls below 10
```

### Step 2 — Read the target

Read the full target file. Identify the exact function body. Understand the
control flow before proposing anything — do not skim.

### Step 3 — Propose two options

Formulate two refactoring options:

**Option A (recommended by default) — minimal**
The smallest change that moves the scanner signal. Typically: extract one or
two private helpers, or add guard clauses to flatten the top nesting level.

**Option B — larger**
A fuller restructure that produces a cleaner result but touches more code.

Present both with a unified diff or clear before/after. For each, state:

| | Option A | Option B |
|---|---|---|
| Expected CC drop | | |
| Lines changed | | |
| Functions touched | | |
| Risk | low / med / high | low / med / high |
| Trade-off | | |

**Default recommendation: Option A**, unless Option B has clearly better payoff
at similar or lower risk. State your recommendation explicitly and why.

Ask: **"Apply Option A, apply Option B, or show a different approach?"**

### Step 4 — Apply on approval

Apply the approved option with the Edit tool. Never edit silently.

If the user declines both options, propose one alternative. If declined again,
stop: *"No approved approach found — target remains at CC=\<N\>."* Do not
retry more than three times total.

Do not change public signatures, return types, module boundaries, or tests.
Extracted helpers must be private (`_` prefix).

### Step 5 — Re-scan to verify

```bash
python3 -m codespy.cli target <file>
```

Report the result:

```
Before:  <function>  CC=<N>
After:   <function>  CC=<M>

✓ VERIFIED — dropped <delta> points          (if signal passed)
✗ NOT VERIFIED — still at <M>, was <N>       (if signal failed)
```

The success signal passes when `function_cc` drops ≥ 2 points **or** falls
below 10. If it does not pass, the refactor did not succeed.

### Step 6 — Continue or stop

**If verified:** state the improvement clearly, then ask:
*"Target is clean. Run `/refactor-loop <path>` to find the next target."*

**If not verified:** recommend reverting and explain what to try differently.
Do not start a second refactor in the same iteration.

---

## Policy summary (operationalized)

| Rule | Behavior |
|---|---|
| Smallest meaningful change | Option A is the default recommendation |
| Two options always | Present both before asking for approval |
| Explain the trade-off | Required for every proposal |
| One function per iteration | Stop after one verified improvement |
| Change budget | One file, one function; stop if scope grows |
| Preserve interfaces | No signature changes, no test edits |
| Scanner is the proof | Re-scan is mandatory; no exceptions |
| Success signal | CC drops ≥2 or falls below 10 |
