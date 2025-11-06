from ortools.sat.python import cp_model

def solve(instance):
    """超级优化版本 - 避免AddMaxEquality，使用最简单的约束"""
    model = cp_model.CpModel()
    n = instance.n
    m = instance.m

    # 预处理：计算每个任务的授权用户
    authorized_users = [set(range(m)) for _ in range(n)]

    for c in instance.constraints:
        if isinstance(c, AuthorisationConstraint):
            for t in range(n):
                if t not in c.tasks:
                    authorized_users[t].discard(c.user)

    # 只为授权的分配创建变量
    x = {}
    for t in range(n):
        for u in authorized_users[t]:
            x[t, u] = model.NewBoolVar(f'x_{t}_{u}')

    # 每个任务分配给恰好一个用户
    for t in range(n):
        model.AddExactlyOne(x[t, u] for u in authorized_users[t])

    # 处理约束
    for c in instance.constraints:
        if isinstance(c, AuthorisationConstraint):
            continue

        elif isinstance(c, BindingOfDutyConstraint):
            common_users = authorized_users[c.t1] & authorized_users[c.t2]
            if not common_users:
                model.AddBoolOr([])
            else:
                for u in common_users:
                    model.Add(x[c.t1, u] == x[c.t2, u])

        elif isinstance(c, SeparationOfDutyConstraint):
            common_users = authorized_users[c.t1] & authorized_users[c.t2]
            for u in common_users:
                model.Add(x[c.t1, u] + x[c.t2, u] <= 1)

        elif isinstance(c, AdvancedConstraint1):
            # 不用AddMaxEquality，用简单的if-then约束
            user_bools = []
            for u in range(m):
                possible_tasks = [t for t in c.tasks if u in authorized_users[t]]
                if possible_tasks:
                    b = model.NewBoolVar(f"ac1_{id(c)}_{u}")
                    # 如果b=1，则至少做一个任务；如果b=0，则不做任何任务
                    model.Add(sum(x[t, u] for t in possible_tasks) >= 1).OnlyEnforceIf(b)
                    model.Add(sum(x[t, u] for t in possible_tasks) == 0).OnlyEnforceIf(b.Not())
                    user_bools.append(b)

            if user_bools:
                model.Add(sum(user_bools) <= c.k)

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

        elif isinstance(c, AdvancedConstraint4):
            team_users = instance.teams[c.team]
            tasks_by_team = []
            for t in range(n):
                for u in team_users:
                    if u in authorized_users[t]:
                        tasks_by_team.append(x[t, u])

            if tasks_by_team:
                model.Add(sum(tasks_by_team) <= c.k)

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

    # 求解器配置
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1  # 单线程，避免开销
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
