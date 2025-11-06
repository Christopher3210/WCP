from ortools.sat.python import cp_model
import sys

# 复制约束类
class AuthorisationConstraint:
    def __init__(self, instance, user, tasks):
        self.user = user
        self.tasks = tasks

class BindingOfDutyConstraint:
    def __init__(self, instance, t1, t2):
        self.t1 = t1
        self.t2 = t2

class SeparationOfDutyConstraint:
    def __init__(self, instance, t1, t2):
        self.t1 = t1
        self.t2 = t2

class AdvancedConstraint1:
    def __init__(self, instance, k, tasks):
        self.tasks = tasks
        self.k = k

class AdvancedConstraint2:
    def __init__(self, instance, k, tasks):
        self.tasks = tasks
        self.k = k

class AdvancedConstraint3:
    def __init__(self, instance, tasks, teams):
        self.tasks = tasks
        self.teams = teams
        self.instance = instance

class AdvancedConstraint4:
    def __init__(self, instance, team, k):
        self.team = team
        self.k = k
        self.instance = instance

class AdvancedConstraint5:
    def __init__(self, instance, team, supervisor):
        self.team = team
        self.supervisor = supervisor
        self.instance = instance

class Instance:
    def __init__(self, n, m, teams, constraints):
        self.n = n
        self.m = m
        self.teams = teams
        self.constraints = constraints

class Solution:
    def __init__(self, instance, sat):
        self.instance = instance
        self.sat = sat
        self.assignment = [-1]*self.instance.n

    def assign_user(self, task, user):
        self.assignment[task] = user

# 你提供的solve函数
def solve(instance):
    """超级优化版本 - 预处理 + 减少变量 + 简单约束"""
    model = cp_model.CpModel()
    n = instance.n
    m = instance.m

    # 【优化1】预处理：计算每个任务的授权用户集合
    authorized_users = [set(range(m)) for _ in range(n)]

    for c in instance.constraints:
        if isinstance(c, AuthorisationConstraint):
            for t in range(n):
                if t not in c.tasks:
                    authorized_users[t].discard(c.user)

    # 【优化2】只为授权的(t,u)对创建变量（大幅减少变量数）
    x = {}
    for t in range(n):
        for u in authorized_users[t]:
            x[t, u] = model.NewBoolVar(f'x_{t}_{u}')

    # 每个任务分配给恰好一个授权用户
    for t in range(n):
        model.AddExactlyOne(x[t, u] for u in authorized_users[t])

    # 处理约束
    for c in instance.constraints:
        if isinstance(c, AuthorisationConstraint):
            continue  # 已在预处理中处理

        # 【优化3】Binding: 只对共同授权用户创建约束
        elif isinstance(c, BindingOfDutyConstraint):
            common_users = authorized_users[c.t1] & authorized_users[c.t2]
            if not common_users:
                model.AddBoolOr([])  # 无解
            else:
                for u in common_users:
                    model.Add(x[c.t1, u] == x[c.t2, u])

        # 【优化4】Separation: 只对共同授权用户创建约束
        elif isinstance(c, SeparationOfDutyConstraint):
            common_users = authorized_users[c.t1] & authorized_users[c.t2]
            for u in common_users:
                model.Add(x[c.t1, u] + x[c.t2, u] <= 1)

        # AC1: 最多k个不同用户
        elif isinstance(c, AdvancedConstraint1):
            user_bools = []
            for u in range(m):
                possible_tasks = [t for t in c.tasks if u in authorized_users[t]]
                if possible_tasks:
                    b = model.NewBoolVar(f"ac1_{id(c)}_{u}")
                    model.Add(sum(x[t, u] for t in possible_tasks) >= 1).OnlyEnforceIf(b)
                    model.Add(sum(x[t, u] for t in possible_tasks) == 0).OnlyEnforceIf(b.Not())
                    user_bools.append(b)

            if user_bools:
                model.Add(sum(user_bools) <= c.k)

        # AC2: 恰好k个不同用户
        elif isinstance(c, AdvancedConstraint2):
            user_bools = []
            for u in range(m):
                possible_tasks = [t for t in c.tasks if u in authorized_users[t]]
                if possible_tasks:
                    b = model.NewBoolVar(f"ac2_{id(c)}_{u}")
                    model.Add(sum(x[t, u] for t in possible_tasks) >= 1).OnlyEnforceIf(b)
                    model.Add(sum(x[t, u] for t in possible_tasks) == 0).OnlyEnforceIf(b.Not())
                    user_bools.append(b)

            if user_bools:
                model.Add(sum(user_bools) == c.k)

        # AC3: 所有任务由某一个团队完成
        elif isinstance(c, AdvancedConstraint3):
            team_selected = []
            for team_idx in c.teams:
                team_bool = model.NewBoolVar(f"ac3_team_{id(c)}_{team_idx}")
                team_selected.append(team_bool)

                team_users = instance.teams[team_idx]
                for t in c.tasks:
                    valid_users = [u for u in team_users if u in authorized_users[t]]
                    if valid_users:
                        model.Add(sum(x[t, u] for u in valid_users) == 1).OnlyEnforceIf(team_bool)
                    else:
                        model.Add(team_bool == 0)

            if team_selected:
                model.AddExactlyOne(team_selected)

        # AC4: 团队工作量限制
        elif isinstance(c, AdvancedConstraint4):
            team_users = instance.teams[c.team]
            tasks_by_team = []
            for t in range(n):
                for u in team_users:
                    if u in authorized_users[t]:
                        tasks_by_team.append(x[t, u])

            if tasks_by_team:
                model.Add(sum(tasks_by_team) <= c.k)

        # AC5: 团队工作则监督者必须工作
        elif isinstance(c, AdvancedConstraint5):
            team_users = instance.teams[c.team]
            supervisor = c.supervisor

            team_tasks = [x[t, u] for t in range(n) for u in team_users if u in authorized_users[t]]
            supervisor_tasks = [x[t, supervisor] for t in range(n) if supervisor in authorized_users[t]]

            if team_tasks and supervisor_tasks:
                team_has_task = model.NewBoolVar(f"ac5_team_{id(c)}")
                model.Add(sum(team_tasks) >= 1).OnlyEnforceIf(team_has_task)
                model.Add(sum(team_tasks) == 0).OnlyEnforceIf(team_has_task.Not())

                supervisor_has_task = model.NewBoolVar(f"ac5_super_{id(c)}")
                model.Add(sum(supervisor_tasks) >= 1).OnlyEnforceIf(supervisor_has_task)
                model.Add(sum(supervisor_tasks) == 0).OnlyEnforceIf(supervisor_has_task.Not())

                model.AddImplication(team_has_task, supervisor_has_task)
            elif team_tasks and not supervisor_tasks:
                model.Add(sum(team_tasks) == 0)

    # 【优化5】求解器配置：单线程避免小实例的并行开销
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = 60.0

    status = solver.Solve(model)

    sat = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    sol = Solution(instance, sat)

    if sat:
        for t in range(n):
            for u in range(m):
                if (t, u) in x and solver.Value(x[t, u]) == 1:
                    sol.assign_user(t, u)
                    break

    return sol


# 测试：课程文档中的示例
print("测试示例1：课程文档中的例子")
print("4个用户，3个任务")
print("约束：")
print("1. u1只能做t1,t2")
print("2. u2只能做t3")
print("3. u4只能做t3")
print("4. t1和t3必须同一人做（binding）")
print("5. t1和t2必须不同人做（separation）")
print("6. t2和t3必须不同人做（separation）")
print("预期解：u3做t1和t3，u1做t2\n")

instance = Instance(
    n=3,  # 3个任务
    m=4,  # 4个用户
    teams=[],
    constraints=[
        AuthorisationConstraint(None, 0, [0, 1]),  # u1(0)只能做t1(0),t2(1)
        AuthorisationConstraint(None, 1, [2]),     # u2(1)只能做t3(2)
        AuthorisationConstraint(None, 3, [2]),     # u4(3)只能做t3(2)
        BindingOfDutyConstraint(None, 0, 2),       # t1和t3同一人
        SeparationOfDutyConstraint(None, 0, 1),    # t1和t2不同人
        SeparationOfDutyConstraint(None, 1, 2),    # t2和t3不同人
    ]
)

try:
    sol = solve(instance)
    print(f"求解状态: {'SAT' if sol.sat else 'UNSAT'}")
    if sol.sat:
        print(f"分配: {sol.assignment}")
        print(f"t1(0)→u{sol.assignment[0]+1}, t2(1)→u{sol.assignment[1]+1}, t3(2)→u{sol.assignment[2]+1}")

        # 验证解
        if sol.assignment[0] == 2 and sol.assignment[1] == 0 and sol.assignment[2] == 2:
            print("✓ 正确！（u3做t1和t3，u1做t2）")
        else:
            print("✗ 错误！结果不符合预期")
    else:
        print("✗ 错误！应该有解但返回UNSAT")
except Exception as e:
    print(f"✗ 运行出错: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
