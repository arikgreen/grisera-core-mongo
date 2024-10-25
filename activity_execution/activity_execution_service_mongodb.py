from typing import Union

from bson import ObjectId

from grisera import (
    ActivityExecutionPropertyIn,
    ActivityExecutionRelationIn,
    ActivityExecutionIn,
    ActivityExecutionOut,
    ActivityExecutionsOut,
    BasicActivityExecutionOut,
    ActivityService, ActivityOut,
)
from grisera import ActivityExecutionService
from grisera import ArrangementService
from grisera import NotFoundByIdModel
from mongo_service.collection_mapping import Collections
from mongo_service.service_mixins import GenericMongoServiceMixin
from grisera import ParticipationService
from grisera import ScenarioService


class ActivityExecutionServiceMongoDB(
    ActivityExecutionService, GenericMongoServiceMixin
):
    """
    Object to handle logic of activities requests
    """

    def __init__(self):
        super().__init__()
        self.model_out_class = ActivityExecutionOut
        self.activity_service = None
        self.arrangement_service: ArrangementService = None
        self.scenario_service: ScenarioService = None
        self.participation_service: ParticipationService = None

    def save_activity_execution(self, activity_execution: ActivityExecutionIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new activity execution

        Args:
            activity_execution (ActivityExecutionIn): Activity execution to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as activity execution object
        """
        related_activity = self.activity_service.get_activity(
            activity_execution.activity_id,
            dataset_id
        )
        related_activity_exists = type(related_activity) is not NotFoundByIdModel
        if (
            activity_execution.activity_id is not None
            and not related_activity_exists
        ):
            return ActivityExecutionOut(
                errors={"errors": "given activity does not exist"}
            )

        related_arrangement = self.arrangement_service.get_arrangement(
            activity_execution.arrangement_id,
            dataset_id
        )
        related_arrangement_exists = type(related_arrangement) is not NotFoundByIdModel
        if (
            activity_execution.arrangement_id is not None
            and not related_arrangement_exists
        ):
            return ActivityExecutionOut(
                errors={"errors": "given arrangement does not exist"}
            )

        return self.activity_service.add_activity_execution(activity_execution, dataset_id)

    def get_multiple(
        self, dataset_id: Union[int, str], query: dict = {}, depth: int = 0, source: str = "", *args, **kwargs
    ):
        """
        Get multiple activity executions based on query. Query has to be adjusted, as activity execution
        documents are embedded within activity documents.
        """
        activity_query = {
            f"{Collections.ACTIVITY_EXECUTION}.{field}": value
            for field, value in query.items()
        }
        activity_results = self.activity_service.get_multiple(
            dataset_id,
            activity_query,
            depth=depth - 1,
            source=Collections.ACTIVITY_EXECUTION,
            projection=self._get_activity_projection(query),
        )
        result = []
        for activity_result in activity_results:
            if "activity_executions" in activity_result:
                activity_executions = activity_result["activity_executions"]
                del activity_result["activity_executions"]
                for activity_execution in activity_executions:
                    self._add_related_documents(
                        activity_execution,
                        dataset_id,
                        depth,
                        source,
                        activity_result,
                    )
                result += activity_executions

        return result

    def get_activity_executions(self, dataset_id: Union[int, str]):
        """
        Send request to mongo api to get activity executions

        Returns:
            Result of request as list of activity executions objects
        """
        activity_execution_dicts = self.get_multiple(dataset_id)
        activity_executions = [
            BasicActivityExecutionOut(**result) for result in activity_execution_dicts
        ]
        return ActivityExecutionsOut(activity_executions=activity_executions)

    def get_single_dict(
        self, id: Union[str, int], dataset_id: Union[int, str], depth: int = 0, source: str = "", *args, **kwargs
    ):
        """
        Get activity execution dict. Activity executions are fetched from activity documents
        """
        activity_execution_object_id = ObjectId(id)
        activity_result = self.activity_service.get_multiple(
            dataset_id,
            {f"{Collections.ACTIVITY_EXECUTION}.id": activity_execution_object_id},
            depth=depth - 1,
            source=Collections.ACTIVITY_EXECUTION,
            projection=self._get_activity_projection(
                {"id": activity_execution_object_id}
            ),
        )
        if (
            len(activity_result) == 0
            or len(activity_result[0][Collections.ACTIVITY_EXECUTION]) == 0
        ):
            return NotFoundByIdModel(
                id=id,
                errors={"errors": "activity execution not found"},
            )
        related_activity = activity_result[0]
        activity_execution_dict = related_activity[Collections.ACTIVITY_EXECUTION][0]
        del related_activity[Collections.ACTIVITY_EXECUTION]
        self._add_related_documents(
            activity_execution_dict, dataset_id, depth, source, related_activity
        )
        return activity_execution_dict

    def get_single(
        self, id: Union[str, int], dataset_id: Union[int, str], depth: int = 0, source: str = "", *args, **kwargs
    ):
        """
        Get single activity execution object.
        """
        result = self.get_single_dict(id, dataset_id, depth, source, *args, **kwargs)
        if type(result) is NotFoundByIdModel:
            return result
        return ActivityExecutionOut(**result)

    def get_activity_execution(
        self,
        activity_execution_id: Union[int, str],
        dataset_id: Union[int, str],
        depth: int = 0,
        source: str = "",
    ):
        """
        Send request to mongo api to get given activity execution

        Args:
            depth (int): specifies how many related entities will be traversed to create the response
            activity_execution_id (int | str): identity of activity execution
            source (str): internal argument for mongo services, used to tell the direction of model fetching.

        Returns:
            Result of request as activity execution object
        """
        return self.get_single(activity_execution_id, dataset_id, depth, source)

    def delete_activity_execution(self, activity_execution_id: Union[int, str], dataset_id: Union[int, str]):
        """
        Send request to mongo api to delete given activity execution
        Args:
            activity_execution_id (int | str): identity of activity execution
        Returns:
            Result of request as activity execution object
        """
        activity_execution = self.get_activity_execution(activity_execution_id, dataset_id)
        if type(activity_execution) is NotFoundByIdModel:
            return NotFoundByIdModel(
                id=activity_execution_id,
                errors={"errors": "activity execution not found"},
            )
        return self.activity_service.remove_activity_execution(activity_execution, dataset_id)

    def update_activity_execution(
        self,
        activity_execution_id: Union[int, str],
        activity_execution: ActivityExecutionPropertyIn,
        dataset_id: Union[int, str],
    ):
        """
        Send request to mongo api to update given participant state
        Args:
            activity_execution_id (int | str): identity of participant state
            activity_execution (ActivityExecutionPropertyIn): Properties to update
        Returns:
            Result of request as participant state object
        """
        existing_activity_execution = self.get_activity_execution(activity_execution_id, dataset_id)
        for field, value in activity_execution.dict().items():
            setattr(existing_activity_execution, field, value)

        return self.activity_service.update_activity_execution(
            activity_execution_id, existing_activity_execution.dict(), dataset_id
        )

    def update_activity_execution_relationships(
        self,
        activity_execution_id: Union[int, str],
        activity_execution: ActivityExecutionRelationIn,
        dataset_id: Union[int, str],
    ):
        """
        Send request to mongo api to update given activity execution relationships
        Args:
            activity_execution_id (int | str): identity of activity execution
            activity_execution (ActivityExecutionIn): Relationships to update
        Returns:
            Result of request as activity execution object
        """
        existing_activity_execution = self.get_activity_execution(activity_execution_id, dataset_id)

        if type(existing_activity_execution) is NotFoundByIdModel:
            return existing_activity_execution

        related_activity = self.activity_service.get_activity(
            activity_execution.activity_id, dataset_id
        )
        related_activity_exists = type(related_activity) is not NotFoundByIdModel
        if not related_activity_exists:
            return ActivityExecutionOut(
                errors={"errors": "given activity does not exist"}
            )

        related_arrangement = self.arrangement_service.get_arrangement(
            activity_execution.arrangement_id,
            dataset_id
        )
        related_arrangement_exists = type(related_arrangement) is not NotFoundByIdModel
        if (
            activity_execution.arrangement_id is not None
            and not related_arrangement_exists
        ):
            return ActivityExecutionOut(
                errors={"errors": "given arrangement does not exist"}
            )

        for field, value in activity_execution.dict().items():
            setattr(existing_activity_execution, field, value)

        return self.activity_service.update_activity_execution(
            activity_execution_id, existing_activity_execution.dict(), dataset_id
        )

    def _add_related_documents(
        self,
        activity_execution: dict,
        dataset_id: Union[int, str],
        depth: int,
        source: str,
        activity: dict,
    ):
        """Recording is taken from previous get query"""
        source = source if source != "" else Collections.ACTIVITY_EXECUTION
        if depth > 0:
            self._add_related_arrangement(activity_execution, dataset_id, depth, source)
            self._add_related_experiments(activity_execution, dataset_id, depth, source)
            self._add_related_participations(activity_execution, dataset_id, depth, source)
            self._add_activity(activity_execution, dataset_id, depth, source, activity)

    def _add_related_experiments(
        self, activity_execution: dict, dataset_id: Union[int, str], depth: int, source: str
    ):
        if depth <= 0 or source == Collections.EXPERIMENT or source == Collections.SCENARIO:
            return

        related_scenarios = self.scenario_service.get_scenario_by_activity_execution(
            activity_execution["id"], dataset_id, depth=depth, multiple=True, source=source
        )
        if type(related_scenarios) is NotFoundByIdModel:
            return

        activity_execution["experiments"] = [
            scenario.experiment for scenario in related_scenarios
        ]

    def _add_related_participations(
        self, activity_execution: dict, dataset_id: Union[int, str], depth: int, source: str
    ):
        if depth <= 0 or source == Collections.PARTICIPATION:
            return

        activity_execution[
            "participations"
        ] = self.participation_service.get_multiple(
            dataset_id,
            {"activity_execution_id": activity_execution["id"]},
            depth=depth - 1,
            source=source,
        )

    def _add_related_arrangement(
        self, activity_execution: dict, dataset_id: Union[int, str], depth: int, source: str
    ):
        has_related_arrangement = activity_execution["arrangement_id"] is not None
        if depth <= 0 or source == Collections.ARRANGEMENT or not has_related_arrangement:
            return

        activity_execution[
            "arrangement"
        ] = self.arrangement_service.get_single_dict(
            activity_execution["arrangement_id"],
            dataset_id,
            depth=depth - 1,
            source=source,
        )

    def _add_activity(
        self, activity_execution: dict, dataset_id: Union[int, str], depth: int, source: str, activity: dict
    ):
        """Activity has already been added related documents"""
        if depth <= 0 or source == Collections.ACTIVITY:
            return

        activity_execution["activity"] = ActivityOut(**activity)

    @staticmethod
    def _get_activity_projection(query):
        return {
            "activity_executions": {"$elemMatch": query} if query else 1,
            "additional_properties": 1,
            "activity": 1,
            "activity_id": 1,
            "arrangement_id": 1,
        }
