from ortools.sat.python import cp_model

def solve(instance):
    """
    Solves the Workflow Satisfiability Problem using CP-SAT solver.

    Args:
        instance: An Instance object containing:
            - n: number of tasks
            - m: number of users
            - teams: list of teams (each team is a list of user indices)
            - constraints: list of constraint objects

    Returns:
        Solution object with sat=True/False and assignment array
    """
    model = cp_model.CpModel()
    n = instance.n  # number of tasks
    m = instance.m  # number of users

    # Decision variables: x[t,u] = 1 if task t is assigned to user u
    x = {(t, u): model.NewBoolVar(f'x_{t}_{u}') for t in range(n) for u in range(m)}

    # Each task must be assigned to exactly one user
    for t in range(n):
        model.AddExactlyOne(x[t, u] for u in range(m))

    # Process constraints
    for c in instance.constraints:
        # Authorisation: user can only do authorized tasks
        if isinstance(c, AuthorisationConstraint):
            for t in range(n):
                if t not in c.tasks:
                    model.Add(x[t, c.user] == 0)

        # Binding of duty: two tasks must be assigned to the same user
        elif isinstance(c, BindingOfDutyConstraint):
            for u in range(m):
                model.Add(x[c.t1, u] == x[c.t2, u])

        # Separation of duty: two tasks must be assigned to different users
        elif isinstance(c, SeparationOfDutyConstraint):
            for u in range(m):
                model.Add(x[c.t1, u] + x[c.t2, u] <= 1)

        # AC1: At most k different users for the given tasks
        elif isinstance(c, AdvancedConstraint1):
            user_used = []
            for u in range(m):
                b = model.NewBoolVar(f"ac1_user_{id(c)}_{u}")
                # b is true iff user u is assigned at least one task from c.tasks
                model.AddMaxEquality(b, [x[t, u] for t in c.tasks])
                user_used.append(b)
            model.Add(sum(user_used) <= c.k)

        # AC2: Exactly k different users for the given tasks
        elif isinstance(c, AdvancedConstraint2):
            user_used = []
            for u in range(m):
                b = model.NewBoolVar(f"ac2_user_{id(c)}_{u}")
                # b is true iff user u is assigned at least one task from c.tasks
                model.AddMaxEquality(b, [x[t, u] for t in c.tasks])
                user_used.append(b)
            model.Add(sum(user_used) == c.k)

        # AC3: All tasks assigned to members of exactly one team from the list
        elif isinstance(c, AdvancedConstraint3):
            # For each team, create a boolean indicating if this team is selected
            team_selected = []
            for team_idx in c.teams:
                team_bool = model.NewBoolVar(f"ac3_team_{id(c)}_{team_idx}")
                team_selected.append(team_bool)

                # If this team is selected, all tasks must be done by this team
                team_users = instance.teams[team_idx]
                for t in c.tasks:
                    model.Add(sum(x[t, u] for u in team_users) == 1).OnlyEnforceIf(team_bool)

            # Exactly one team must be selected
            model.AddExactlyOne(team_selected)

        # AC4: Team workload limit - at most k tasks assigned to team members
        elif isinstance(c, AdvancedConstraint4):
            team_users = instance.teams[c.team]
            model.Add(sum(x[t, u] for t in range(n) for u in team_users) <= c.k)

        # AC5: If any team member is assigned a task, supervisor must be assigned too
        elif isinstance(c, AdvancedConstraint5):
            team_users = instance.teams[c.team]
            supervisor = c.supervisor

            # Create boolean for whether team has any task
            team_has_task = model.NewBoolVar(f"ac5_team_{id(c)}")
            model.AddMaxEquality(team_has_task, [x[t, u] for t in range(n) for u in team_users])

            # Create boolean for whether supervisor has any task
            supervisor_has_task = model.NewBoolVar(f"ac5_super_{id(c)}")
            model.AddMaxEquality(supervisor_has_task, [x[t, supervisor] for t in range(n)])

            # If team has task, supervisor must have task
            model.AddImplication(team_has_task, supervisor_has_task)

    # Solver configuration for better performance
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 8  # Parallel search
    solver.parameters.max_time_in_seconds = 60.0  # 60 second timeout per instance
    solver.parameters.log_search_progress = False  # Reduce output

    status = solver.Solve(model)

    sat = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    sol = Solution(instance, sat)

    if sat:
        for t in range(n):
            for u in range(m):
                if solver.Value(x[t, u]) == 1:
                    sol.assign_user(t, u)
                    break

    return sol
