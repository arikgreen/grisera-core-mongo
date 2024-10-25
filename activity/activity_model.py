from typing import Optional, List

from grisera import BasicActivityOut, BasicActivityExecutionOut


class BasicActivityOutToMongo(BasicActivityOut):
    activity_executions: Optional[List[BasicActivityExecutionOut]]
