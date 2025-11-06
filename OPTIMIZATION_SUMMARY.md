# Workflow Satisfiability Solver - Performance Optimizations

## Overview
This document summarizes the key optimizations made to improve the CP-SAT solver performance for the Workflow Satisfiability Problem.

## Critical Bug Fix

### AC3 Constraint (FIXED)
**Problem:** The original implementation only checked if at least one team could perform all tasks, but didn't prevent tasks from being assigned to users outside those teams.

**Original Code:**
```python
# Only checks if team CAN do tasks, doesn't enforce exclusivity
for team in c.teams:
    b = model.NewBoolVar(f"ac3_teamok_{id(c)}_{team}")
    for t in c.tasks:
        allowed_users = instance.teams[team]
        model.Add(sum(x[(t,u)] for u in allowed_users) >= 1).OnlyEnforceIf(b)
    team_ok.append(b)
model.Add(sum(team_ok) >= 1)
```

**Fixed Code:**
```python
# Ensures exactly one team is selected and ALL tasks use only that team
team_selected = []
for team_idx in c.teams:
    team_bool = model.NewBoolVar(f"ac3_team_{id(c)}_{team_idx}")
    team_selected.append(team_bool)

    team_users = instance.teams[team_idx]
    for t in c.tasks:
        # When team is selected, each task MUST be done by this team (== 1)
        model.Add(sum(x[t, u] for u in team_users) == 1).OnlyEnforceIf(team_bool)

# Exactly one team must be selected
model.AddExactlyOne(team_selected)
```

## Performance Optimizations

### 1. AC1 & AC2 - Using AddMaxEquality
**Before:** 3 constraints per user (2 implications + 1 boolean definition)
```python
b = model.NewBoolVar(f"ac1_used_{id(c)}_{u}")
model.Add(sum(x[(t,u)] for t in c.tasks)>=1).OnlyEnforceIf(b)
model.Add(sum(x[(t,u)] for t in c.tasks)==0).OnlyEnforceIf(b.Not())
```

**After:** 1 constraint per user (CP-SAT's native construct)
```python
b = model.NewBoolVar(f"ac1_user_{id(c)}_{u}")
model.AddMaxEquality(b, [x[t, u] for t in c.tasks])
```

**Benefits:**
- Fewer constraints in the model
- CP-SAT can propagate this constraint more efficiently
- Cleaner code

### 2. AC5 - Using AddMaxEquality
**Before:** Manual definition with implications
```python
team_has_task = model.NewBoolVar(f"team_{c.team}_hasTask")
model.Add(sum(x[(t,u)] for t in range(n) for u in team_users) >= 1).OnlyEnforceIf(team_has_task)
model.Add(sum(x[(t,u)] for t in range(n) for u in team_users) == 0).OnlyEnforceIf(team_has_task.Not())
```

**After:** Native CP-SAT construct
```python
team_has_task = model.NewBoolVar(f"ac5_team_{id(c)}")
model.AddMaxEquality(team_has_task, [x[t, u] for t in range(n) for u in team_users])
```

### 3. Solver Parameters
Added key performance parameters:
```python
solver.parameters.num_search_workers = 8  # Parallel search
solver.parameters.max_time_in_seconds = 60.0  # Prevent infinite loops
solver.parameters.log_search_progress = False  # Reduce I/O overhead
```

**num_search_workers = 8:**
- Enables parallel search using multiple threads
- Explores different parts of the search space simultaneously
- Typically gives 2-4x speedup on multi-core systems

**max_time_in_seconds = 60:**
- Prevents solver from running indefinitely on hard instances
- Returns UNKNOWN status if timeout is reached
- Important for batches 8 & 9 which are expected to be hard

### 4. Code Structure Improvements
- Changed `if` chain to `elif` chain (prevents unnecessary checks)
- More descriptive variable names
- Added comprehensive comments

## Expected Performance Improvements

Based on the reference times in the assignment:

| Batch | Constraints | Ref. Time | Expected Improvement |
|-------|-------------|-----------|---------------------|
| 1 | Basic only | 0.1s | ✓ Should match or beat |
| 2 | Basic + AC1 | 0.7s | ✓ Should match or beat |
| 3 | Basic + AC2 | 6.4s | ✓ Should improve significantly |
| 4 | Basic + AC3 | 1.2s | ✓ Critical fix, should now pass |
| 5 | Basic + AC4 | 0.5s | ✓ Should match or beat |
| 6 | Basic + AC5 | 0.7s | ✓ Should improve |
| 7 | All constraints | 1.1s | ✓ Should improve significantly |
| 8 | Hard instances | 6.0s | ~ May timeout on some |
| 9 | Harder instances | 16.7s | ~ May timeout on most |

## Testing Instructions

1. Run the test cell in the notebook:
```python
for batch_index in range(1, 10):
    test_batch(batch_index)
```

2. Compare your times with the reference times
3. Check that all tests pass (green output)

## Further Optimizations (If Needed)

If performance is still not sufficient, consider:

1. **Variable ordering heuristics:** Add hints to guide the solver
2. **Symmetry breaking:** Add constraints to eliminate symmetric solutions
3. **Preprocessing:** Analyze constraints to simplify the model before solving
4. **Alternative formulations:** Use integer variables instead of boolean for some constraints
5. **Warm start:** Provide an initial solution if you can find one with a heuristic

## Common Issues

### Issue: Timeout on hard instances (Batches 8-9)
**Solution:** This is expected. Focus on getting Batches 1-7 working efficiently.

### Issue: Wrong results
**Solution:** Check that your constraint implementation matches the specification exactly. Pay special attention to "at most k" vs "exactly k".

### Issue: Slow on small instances
**Solution:** Reduce `num_search_workers` for small instances (overhead may dominate).
