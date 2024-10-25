from typing import Union

from bson import ObjectId
from grisera import (
    ActivityExecutionIn,
    ActivityExecutionOut,
    BasicActivityExecutionOut,
)

from grisera import ActivityExecutionService
from grisera import (
    ActivityIn,
    ActivityOut,
    ActivitiesOut,
    BasicActivityOut,
)
from grisera import ActivityService
from grisera import NotFoundByIdModel

from activity.activity_model import BasicActivityOutToMongo
from mongo_service.collection_mapping import Collections
from mongo_service.mongo_api_service import MongoApiService
from mongo_service.service_mixins import GenericMongoServiceMixin


class ActivityServiceMongoDB(ActivityService, GenericMongoServiceMixin):
    """
    Object to handle logic of activity requests
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.model_out_class = ActivityOut
        self.activity_execution_service: ActivityExecutionService = None

    def save_activity(self, activity: ActivityIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new activity

        Args:
            activity (ActivityIn): Activity to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as activity object
        """
        return self.create(activity, dataset_id)

    def get_activities(self, dataset_id: Union[int, str], query: dict = {}):
        """
        Send request to mongo api to get all activities

        Args:
            dataset_id (int | str): name of dataset
            query: Query to mongo api. Empty by default.

        Returns:
            Result of request as list of activity objects
        """
        results_dict = self.get_multiple(dataset_id, query)
        activities = [BasicActivityOut(**result) for result in results_dict]
        return ActivitiesOut(activities=activities)

    def get_activity(
        self, activity_id: Union[int, str], dataset_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given activity
        Args:
            activity_id (int | str): identity of activity
            dataset_id (int | str): name of dataset
            depth(int): specifies how many related entities will be traversed to create the response
            source (str): internal argument for mongo services, used to tell the direction of model fetching.

        Returns:
            Result of request as activity object
        """
        return self.get_single(activity_id, dataset_id, depth, source)

    def delete_activity(self, activity_id: int, dataset_id: Union[int, str]):
        """
        Send request to mongo api to delete given activity
        Args:
            activity_id (int): ID of activity
            dataset_id (int | str): name of dataset
        Returns:
            Result of request as activity object
        """
        return self.delete(activity_id, dataset_id)

    def update_activity(self, activity_id: int, activity: ActivityIn, dataset_id: Union[int, str]):
        """
        Send request to graph api to update given activity
        Args:
            activity_id (int): ID of activity
            activity (ActivityIn): Activity to be updated
            dataset_id (int | str): name of dataset
        Returns:
            Result of request as activity object
        """
        return self.update(activity_id, activity, dataset_id)

    def add_activity_execution(self, activity_execution: ActivityExecutionIn, dataset_id: Union[int, str]):
        """
        Add activity execution to activity. Activity execution is embedded in related activity.

        Args:
            activity_execution (ActivityExecutionIn): activity execution to add
            dataset_id (int | str): name of dataset

        Returns:
            Added activity execution as BasicActivityExecutionOut object
        """
        activity_execution_dict = activity_execution.dict()
        activity_execution_dict["id"] = str(ObjectId())
        activity_execution = BasicActivityExecutionOut(**activity_execution_dict)

        activity_id = activity_execution.activity_id
        activity = self.get_single_dict(activity_id, dataset_id)
        activity_executions = activity.get(Collections.ACTIVITY_EXECUTION, [])
        if activity_executions is None:
            activity_executions = []
        activity_executions.append(activity_execution)
        activity[Collections.ACTIVITY_EXECUTION] = activity_executions

        self.update(activity_id, BasicActivityOutToMongo(**activity), dataset_id)
        return ActivityExecutionOut(**activity_execution_dict)

    def update_activity_execution(
        self,
        activity_execution_id: Union[int, str],
        activity_execution_dict: dict,
        dataset_id: Union[int, str]
    ):
        """
        Edit activity execution in activity. Activity execution is embedded in related activity.

        Args:
            activity_execution_id (Union[int, str]): id of activity execution that is to be updated
            activity_execution_dict (dict): new version of activity execution
            dataset_id (int | str): name of dataset

        Returns:
            Updated activity execution
        """
        activity_id = activity_execution_dict["activity_id"]
        activity = self.get_single_dict(activity_id, dataset_id)
        if type(activity) is NotFoundByIdModel:
            return NotFoundByIdModel(
                id=activity_execution_id,
                errors={
                    "errors": "activity related to given activity execution not found"
                },
            )

        to_update_index = self._get_activity_execution_index_from_activity(
            activity, activity_execution_id
        )
        if to_update_index is None:
            return NotFoundByIdModel(
                id=activity_execution_id,
                errors={"errors": "activity execution not found"},
            )
        activity_executions = activity[Collections.ACTIVITY_EXECUTION]
        activity_executions[to_update_index] = BasicActivityExecutionOut(**activity_execution_dict)
        self.update(activity_id, BasicActivityOutToMongo(**activity), dataset_id)
        return ActivityExecutionOut(**activity_execution_dict)

    def remove_activity_execution(self, activity_execution: ActivityExecutionOut, dataset_id: Union[int, str]):
        """
        Remove activity execution from activity. Activity execution is embedded in related activity.

        Args:
            activity_execution (ActivityExecutionOut): activity execution to remove
            dataset_id (int | str): name of dataset

        Returns:
            Removed activity execution
        """
        activity_id = activity_execution.activity_id
        activity = self.get_single_dict(activity_id, dataset_id)
        if type(activity) is NotFoundByIdModel:
            return NotFoundByIdModel(
                id=activity_execution.id,
                errors={
                    "errors": "activity related to given activity execution not found"
                },
            )

        to_remove_index = self._get_activity_execution_index_from_activity(
            activity, activity_execution.id
        )
        if to_remove_index is None:
            return NotFoundByIdModel(
                id=activity_execution.id,
                errors={"errors": "activity execution not found"},
            )
        del activity[Collections.ACTIVITY_EXECUTION][to_remove_index]

        self.update(activity_id, BasicActivityOutToMongo(**activity), dataset_id)
        return activity_execution

    def _get_activity_execution_index_from_activity(
        self, activity_dict: dict, activity_execution_id: Union[str, int]
    ):
        """
        Activity execution is embedded within activity model
        """
        activity_executions = activity_dict[Collections.ACTIVITY_EXECUTION]
        return next(
            (
                i
                for i, oi in enumerate(activity_executions)
                if ObjectId(oi["id"]) == ObjectId(activity_execution_id)
            ),
            None,
        )

    def _add_related_documents(self, activity: dict, dataset_id: Union[int, str], depth: int, source: str):
        if depth > 0:
            self._add_related_activity_executions(activity, dataset_id, depth, source)

    def _add_related_activity_executions(self, activity: dict, dataset_id: Union[int, str], depth: int, source: str):
        """
        Observable information is embedded within recording model
        """
        has_activity_executions = Collections.ACTIVITY_EXECUTION in activity and activity[Collections.ACTIVITY_EXECUTION] is not None
        if source != Collections.ACTIVITY_EXECUTION and has_activity_executions:
            for ae in activity[Collections.ACTIVITY_EXECUTION]:
                self.activity_execution_service._add_related_documents(
                    ae, dataset_id, depth - 1, Collections.ACTIVITY, activity
                )
