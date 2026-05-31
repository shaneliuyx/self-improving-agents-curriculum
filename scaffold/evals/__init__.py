# evals package
from evals.tasks import TASKS, Task
from evals.run import run_evals, score_prompt, EvalReport

__all__ = ["TASKS", "Task", "run_evals", "score_prompt", "EvalReport"]
