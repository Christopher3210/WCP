from ortools.sat.python import cp_model

def solve(instance):
    """
    工作流可满足性问题求解器

    保证正确性的简单实现，包含所有基本和高级约束
    """
    model = cp_model.CpModel()
    n = instance.n  # 任务数
    m = instance.m  # 用户数

    # 创建决策变量：x[t,u] = 1 表示任务t分配给用户u
    x = {}
    for t in range(n):
        for u in range(m):
            x[t, u] = model.NewBoolVar(f'x_{t}_{u}')

    # 每个任务必须分配给恰好一个用户
    for t in range(n):
        model.AddExactlyOne([x[t, u] for u in range(m)])

    # 处理约束
    for c in instance.constraints:
        # Authorisation: 用户只能做授权的任务
        if isinstance(c, AuthorisationConstraint):
            # 该用户不能做未授权的任务
            for t in range(n):
                if t not in c.tasks:
                    model.Add(x[t, c.user] == 0)

        # Binding of duty: 两个任务必须分配给同一用户
        elif isinstance(c, BindingOfDutyConstraint):
            for u in range(m):
                model.Add(x[c.t1, u] == x[c.t2, u])

        # Separation of duty: 两个任务必须分配给不同用户
        elif isinstance(c, SeparationOfDutyConstraint):
            for u in range(m):
                model.Add(x[c.t1, u] + x[c.t2, u] <= 1)

        # AC1: 最多k个不同用户完成这些任务
        elif isinstance(c, AdvancedConstraint1):
            user_used = []
            for u in range(m):
                # 创建一个布尔变量表示用户u是否做了这些任务中的至少一个
                b = model.NewBoolVar(f'ac1_user_{id(c)}_{u}')
                # 如果用户u做了至少一个任务，b=1
                model.Add(sum(x[t, u] for t in c.tasks) >= 1).OnlyEnforceIf(b)
                # 如果用户u没做任何任务，b=0
                model.Add(sum(x[t, u] for t in c.tasks) == 0).OnlyEnforceIf(b.Not())
                user_used.append(b)
            # 最多k个用户
            model.Add(sum(user_used) <= c.k)

        # AC2: 恰好k个不同用户完成这些任务
        elif isinstance(c, AdvancedConstraint2):
            user_used = []
            for u in range(m):
                b = model.NewBoolVar(f'ac2_user_{id(c)}_{u}')
                model.Add(sum(x[t, u] for t in c.tasks) >= 1).OnlyEnforceIf(b)
                model.Add(sum(x[t, u] for t in c.tasks) == 0).OnlyEnforceIf(b.Not())
                user_used.append(b)
            # 恰好k个用户
            model.Add(sum(user_used) == c.k)

        # AC3: 所有任务必须由某一个团队的成员完成
        elif isinstance(c, AdvancedConstraint3):
            # 为每个可选团队创建一个布尔变量
            team_vars = []
            for team_idx in c.teams:
                team_var = model.NewBoolVar(f'ac3_team_{id(c)}_{team_idx}')
                team_vars.append(team_var)

                # 如果选择了这个团队，那么所有任务必须由该团队成员完成
                team_members = instance.teams[team_idx]
                for t in c.tasks:
                    # 该任务必须由团队成员之一完成
                    model.Add(sum(x[t, u] for u in team_members) == 1).OnlyEnforceIf(team_var)

            # 必须恰好选择一个团队
            model.AddExactlyOne(team_vars)

        # AC4: 团队成员做的任务总数不超过k
        elif isinstance(c, AdvancedConstraint4):
            team_members = instance.teams[c.team]
            # 统计团队成员完成的任务总数
            total_tasks = sum(x[t, u] for t in range(n) for u in team_members)
            model.Add(total_tasks <= c.k)

        # AC5: 如果团队成员做了任何任务，监督者也必须做任务
        elif isinstance(c, AdvancedConstraint5):
            team_members = instance.teams[c.team]
            supervisor = c.supervisor

            # 团队是否做了任务
            team_has_task = model.NewBoolVar(f'ac5_team_{id(c)}')
            model.Add(sum(x[t, u] for t in range(n) for u in team_members) >= 1).OnlyEnforceIf(team_has_task)
            model.Add(sum(x[t, u] for t in range(n) for u in team_members) == 0).OnlyEnforceIf(team_has_task.Not())

            # 监督者是否做了任务
            supervisor_has_task = model.NewBoolVar(f'ac5_super_{id(c)}')
            model.Add(sum(x[t, supervisor] for t in range(n)) >= 1).OnlyEnforceIf(supervisor_has_task)
            model.Add(sum(x[t, supervisor] for t in range(n)) == 0).OnlyEnforceIf(supervisor_has_task.Not())

            # 如果团队做了任务，监督者必须也做任务
            model.AddImplication(team_has_task, supervisor_has_task)

    # 配置求解器
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1  # 单线程
    solver.parameters.max_time_in_seconds = 60.0

    # 求解
    status = solver.Solve(model)

    # 构造解
    sat = (status == cp_model.OPTIMAL or status == cp_model.FEASIBLE)
    sol = Solution(instance, sat)

    if sat:
        for t in range(n):
            for u in range(m):
                if solver.Value(x[t, u]) == 1:
                    sol.assign_user(t, u)
                    break

    return sol
