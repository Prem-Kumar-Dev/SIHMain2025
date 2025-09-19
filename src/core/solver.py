from typing import List

from src.core.models import TrainRequest, NetworkModel, ScheduleItem
from src.core.greedy_scheduler import schedule_trains as greedy_schedule
from src.core.milp_scheduler import schedule_trains_milp


def schedule_trains(trains: List[TrainRequest], network: NetworkModel, solver: str = "greedy", milp_time_limit: int | None = None) -> List[ScheduleItem]:
    if solver == "milp":
        try:
            return schedule_trains_milp(network, trains, time_limit=milp_time_limit)
        except Exception:
            # Fallback to greedy if MILP unsupported scenario or times out
            return greedy_schedule(trains, network)
    return greedy_schedule(trains, network)
