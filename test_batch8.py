#!/usr/bin/env python3
"""Quick test script for batch8"""

import sys
import time
import re
from ortools.sat.python import cp_model


# ==================== Classes from notebook ====================
class AuthorisationConstraint:
    def __init__(self, instance, user, tasks):
        assert user >= 0 and user < instance.m
        assert all(t >= 0 and t < instance.n for t in tasks)
        self.user = user
        self.tasks = tasks

    def is_satisfied(self, solution):
        for task in set(range(solution.instance.n)) - set(self.tasks):
            if solution.assignment[task] == self.user:
                return False
        return True


class BindingOfDutyConstraint:
    def __init__(self, instance, t1, t2):
        assert 0 <= t1 < instance.n
        assert t2 >= 0 and t2 < instance.n
        self.t1 = t1
        self.t2 = t2

    def is_satisfied(self, solution):
        return solution.assignment[self.t1] == solution.assignment[self.t2]


class SeparationOfDutyConstraint:
    def __init__(self, instance, t1, t2):
        assert 0 <= t1 < instance.n
        assert t2 >= 0 and t2 < instance.n
        self.t1 = t1
        self.t2 = t2

    def is_satisfied(self, solution):
        return solution.assignment[self.t1] != solution.assignment[self.t2]


class AdvancedConstraint1:
    def __init__(self, instance, k, tasks):
        assert 0 < k <= instance.n
        assert all(0 <= task <= instance.n for task in tasks)
        self.tasks = tasks
        self.k = k

    def is_satisfied(self, solution):
        return len(set(solution.assignment[task] for task in self.tasks)) <= self.k


class AdvancedConstraint2:
    def __init__(self, instance, k, tasks):
        assert 1 <= k <= instance.n
        assert all(0 <= t < instance.n for t in tasks)
        self.tasks = tasks
        self.k = k

    def is_satisfied(self, solution):
        return len(set(solution.assignment[t] for t in self.tasks)) == self.k


class AdvancedConstraint3:
    def __init__(self, instance, tasks, teams):
        assert all(0 <= t < instance.n for t in tasks)
        assert all(0 <= team < len(instance.teams) for team in teams)
        self.tasks = tasks
        self.teams = teams
        self.instance = instance

    def is_satisfied(self, solution):
        return any(all(solution.assignment[t] in self.instance.teams[team] for t in self.tasks) for team in self.teams)


class AdvancedConstraint4:
    def __init__(self, instance, team, k):
        assert 0 <= k < instance.n
        assert 0 <= team < len(instance.teams)
        self.team = team
        self.k = k
        self.instance = instance

    def is_satisfied(self, solution):
        return sum(1 for t in range(self.instance.n) if solution.assignment[t] in self.instance.teams[self.team]) <= self.k


class AdvancedConstraint5:
    def __init__(self, instance, team, supervisor):
        assert 0 <= team < len(instance.teams)
        assert 0 <= supervisor < instance.m
        self.team = team
        self.supervisor = supervisor
        self.instance = instance

    def is_satisfied(self, solution):
        return not any(solution.assignment[t] in self.instance.teams[self.team] for t in range(self.instance.n)) \
            or any(solution.assignment[t] == self.supervisor for t in range(self.instance.n))


class Instance:
    def __init__(self, filename):
        def parse_task(string):
            return int(re.match(r't(\d+)', string).group(1)) - 1

        def parse_user(string):
            return int(re.match(r'u(\d+)', string).group(1)) - 1

        def parse_team(string):
            return int(re.match(r'team(\d+)', string).group(1)) - 1

        if filename is None:
            return

        with open(filename, 'r') as f:
            self.n = int(re.match(r'^\s*#Tasks:\s+(\d+)\s*$', f.readline(), re.IGNORECASE).group(1))
            self.m = int(re.match(r'^\s*#Users:\s+(\d+)\s*$', f.readline(), re.IGNORECASE).group(1))

            t = int(re.match(r'^\s*#Teams:\s+(\d+)\s*$', f.readline(), re.IGNORECASE).group(1))
            self.teams = []
            for team_index in range(t):
                self.teams.append(list(map(parse_user, f.readline().strip().lower().split())))

            c = int(re.match(r'^\s*#Constraints:\s+(\d+)\s*$', f.readline(), re.IGNORECASE).group(1))

            self.constraints = []
            for line_index in range(c):
                line = f.readline().strip().lower()
                values = line.split()

                if values[0] == 'authorisations':
                    self.constraints.append(AuthorisationConstraint(
                        self, parse_user(values[1]), list(map(parse_task, values[2:]))))

                elif values[0] == 'binding-of-duty':
                    self.constraints.append(BindingOfDutyConstraint(self, parse_task(values[1]), parse_task(values[2])))

                elif values[0] == 'separation-of-duty':
                    self.constraints.append(SeparationOfDutyConstraint(self, parse_task(values[1]), parse_task(values[2])))

                elif values[0] == 'ac1':
                    self.constraints.append(AdvancedConstraint1(self, int(values[1]), list(map(parse_task, values[2:]))))

                elif values[0] == 'ac2':
                    self.constraints.append(AdvancedConstraint2(self, int(values[1]), list(map(parse_task, values[2:]))))

                elif values[0] == 'ac3':
                    teams = []
                    index = 1
                    while values[index].startswith('team'):
                        teams.append(parse_team(values[index]))
                        index += 1

                    self.constraints.append(AdvancedConstraint3(self, list(map(parse_task, values[index:])), teams))

                elif values[0] == 'ac4':
                    self.constraints.append(AdvancedConstraint4(self, parse_team(values[1]), int(values[2])))

                elif values[0] == 'ac5':
                    self.constraints.append(AdvancedConstraint5(self, parse_team(values[1]), parse_user(values[2])))

                else:
                    raise Exception(f'Unknown constraint {values[0]}.')


class Solution:
    def __init__(self, instance, sat):
        self.instance = instance
        self.sat = sat
        self.assignment = [-1]*self.instance.n

    def assign_user(self, task, user):
        if task < 0 or task >= self.instance.n:
            raise Exception(f'Task {task} is outside the range.')
        if user < 0 or user >= self.instance.m:
            raise Exception(f'User {user} is outside the range.')
        self.assignment[task] = user


# ==================== Solve function from notebook ====================
def solve(instance):
    model = cp_model.CpModel()
    n = instance.n
    m = instance.m

    # ========== 预处理 - 计算每个任务的可用用户 ==========
    available = [set(range(m)) for _ in range(n)]

    # Authorisation：把被禁止的 (task, user) 去掉
    for c in instance.constraints:
        if isinstance(c, AuthorisationConstraint):
            for t in range(n):
                if t not in c.tasks:
                    available[t].discard(c.user)

    # Binding-of-duty：两任务的 domain 取交集（若为空直接 UNSAT）
    for c in instance.constraints:
        if isinstance(c, BindingOfDutyConstraint):
            common = available[c.t1] & available[c.t2]
            if not common:
                return Solution(instance, False)
            available[c.t1] = common
            available[c.t2] = common

    # —— AC3 安全剪枝：仅允许来自给定 teams 的用户（并集）——
    for c in instance.constraints:
        if isinstance(c, AdvancedConstraint3):
            allowed = set()
            for team in c.teams:
                allowed |= set(instance.teams[team])
            for t in c.tasks:
                available[t] &= allowed
                if not available[t]:
                    return Solution(instance, False)

    # ========== 使用受限 domain 创建变量 ==========
    task = []
    for t in range(n):
        if not available[t]:
            return Solution(instance, False)
        task.append(
            model.NewIntVarFromDomain(
                cp_model.Domain.FromValues(sorted(available[t])),
                f"task_{t}"
            )
        )

    # 小工具：缓存 "task[t] == u" 的布尔文字，避免重复建模
    eq_lit_cache = {}
    def eq_lit(t, u):
        key = (t, u)
        if key not in eq_lit_cache:
            b = model.NewBoolVar(f"lit_t{t}_u{u}")
            model.Add(task[t] == u).OnlyEnforceIf(b)
            model.Add(task[t] != u).OnlyEnforceIf(b.Not())
            eq_lit_cache[key] = b
        return eq_lit_cache[key]

    # ========== 添加约束 ==========
    for c in instance.constraints:
        if isinstance(c, AuthorisationConstraint):
            # 已在 domain 中处理
            pass

        elif isinstance(c, BindingOfDutyConstraint):
            model.Add(task[c.t1] == task[c.t2])

        elif isinstance(c, SeparationOfDutyConstraint):
            model.Add(task[c.t1] != task[c.t2])

        # AC1：至多 k 个不同用户执行 c.tasks（和二元变量版本完全相同的逻辑）
        elif isinstance(c, AdvancedConstraint1):
            users_for_c = sorted(set().union(*(available[t] for t in c.tasks)))
            used = []
            for u in users_for_c:
                b = model.NewBoolVar(f"ac1_used_{id(c)}_{u}")
                # lits[i] = 1 iff task[c.tasks[i]] == u，等价于二元变量x[(t,u)]
                lits = [eq_lit(t, u) for t in c.tasks if u in available[t]]
                if lits:
                    # 和二元版本完全一样：sum(x[(t,u)] for t in c.tasks) >= 1
                    model.Add(sum(lits) >= 1).OnlyEnforceIf(b)
                    model.Add(sum(lits) == 0).OnlyEnforceIf(b.Not())
                else:
                    model.Add(b == 0)
                used.append(b)
            model.Add(sum(used) <= c.k)

        # AC2：恰好 k 个不同用户执行 c.tasks
        elif isinstance(c, AdvancedConstraint2):
            users_for_c = sorted(set().union(*(available[t] for t in c.tasks)))
            used = []
            for u in users_for_c:
                b = model.NewBoolVar(f"ac2_{id(c)}_u{u}")
                lits = [eq_lit(t, u) for t in c.tasks if u in available[t]]
                if lits:
                    model.Add(sum(lits) >= 1).OnlyEnforceIf(b)
                    model.Add(sum(lits) == 0).OnlyEnforceIf(b.Not())
                else:
                    model.Add(b == 0)
                used.append(b)
            model.Add(sum(used) == c.k)

        # AC3：至少有一个给定 team 能"单独完成"这些任务
        elif isinstance(c, AdvancedConstraint3):
            team_ok = []
            for team in c.teams:
                b = model.NewBoolVar(f"ac3_teamok_{id(c)}_{team}")
                team_ok.append(b)
                allowed_users = set(instance.teams[team])
                for t in c.tasks:
                    lits = [eq_lit(t, u) for u in allowed_users if u in available[t]]
                    if lits:
                        model.AddBoolOr(lits).OnlyEnforceIf(b)
                    else:
                        model.Add(b == 0)
            model.Add(sum(team_ok) >= 1)

        # AC4：team 的成员最多执行 k 个任务
        elif isinstance(c, AdvancedConstraint4):
            team_users = set(instance.teams[c.team])
            fixed = 0
            indicators = []

            for t in range(n):
                cand = [u for u in available[t] if u in team_users]
                if not cand:
                    continue
                if set(available[t]).issubset(team_users):
                    fixed += 1
                else:
                    b = model.NewBoolVar(f"ac4_t{t}_team{c.team}")
                    lits = [eq_lit(t, u) for u in cand]
                    model.AddBoolOr(lits).OnlyEnforceIf(b)
                    model.AddBoolAnd([l.Not() for l in lits]).OnlyEnforceIf(b.Not())
                    indicators.append(b)

            if fixed > c.k:
                return Solution(instance, False)
            if indicators:
                model.Add(sum(indicators) <= c.k - fixed)

        # AC5: 如果某个 team 有参与任务 -> 监督者必须至少执行一个任务
        elif isinstance(c, AdvancedConstraint5):
            team_users = set(instance.teams[c.team])
            supervisor = c.supervisor

            team_lits = [eq_lit(t, u) for t in range(n) for u in team_users if u in available[t]]
            sup_lits = [eq_lit(t, supervisor) for t in range(n) if supervisor in available[t]]

            if not sup_lits:
                if team_lits:
                    return Solution(instance, False)
            elif team_lits:
                team_has_task = model.NewBoolVar(f"team{c.team}_hasTask")
                model.Add(sum(team_lits) >= 1).OnlyEnforceIf(team_has_task)
                model.Add(sum(team_lits) == 0).OnlyEnforceIf(team_has_task.Not())

                supervisor_has_task = model.NewBoolVar(f"sup{supervisor}_hasTask")
                model.Add(sum(sup_lits) >= 1).OnlyEnforceIf(supervisor_has_task)
                model.Add(sum(sup_lits) == 0).OnlyEnforceIf(supervisor_has_task.Not())

                model.AddImplication(team_has_task, supervisor_has_task)

    # ========== 求解器参数 ==========
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 8
    solver.parameters.linearization_level = 2

    status = solver.Solve(model)
    sat = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    sol = Solution(instance, sat)
    if sat:
        for t in range(n):
            sol.assign_user(t, solver.Value(task[t]))
    return sol


# ==================== Test function ====================
def test_batch8():
    print("Testing batch8...")
    print("=" * 60)

    passed_count = 0
    failed_tests = []

    for i in range(1, 11):
        filename = f'batch8/inst_{i}.txt'
        expected_sat = (i % 2 == 1)

        try:
            instance = Instance(filename)

            start_time = time.perf_counter()
            solution = solve(instance)
            end_time = time.perf_counter()

            elapsed_ms = (end_time - start_time) * 1000

            # Check correctness
            passed = (solution.sat == expected_sat)
            if solution.sat:
                broken = [c for c in instance.constraints if not c.is_satisfied(solution)]
                if broken:
                    passed = False
                    print(f"  inst_{i}.txt: FAIL - {len(broken)} constraints broken ({elapsed_ms:.0f} ms)")
                    failed_tests.append(i)
                else:
                    print(f"  inst_{i}.txt: PASS ({elapsed_ms:.0f} ms)")
                    passed_count += 1
            else:
                if passed:
                    print(f"  inst_{i}.txt: PASS ({elapsed_ms:.0f} ms)")
                    passed_count += 1
                else:
                    print(f"  inst_{i}.txt: FAIL - expected {'SAT' if expected_sat else 'UNSAT'}, got {'SAT' if solution.sat else 'UNSAT'} ({elapsed_ms:.0f} ms)")
                    failed_tests.append(i)

        except Exception as e:
            print(f"  inst_{i}.txt: ERROR - {e}")
            failed_tests.append(i)

    print("=" * 60)
    print(f"Results: {passed_count}/10 tests passed")

    if failed_tests:
        print(f"Failed tests: {failed_tests}")
        return False
    else:
        print("All batch8 tests passed!")
        return True


if __name__ == "__main__":
    success = test_batch8()
    sys.exit(0 if success else 1)
