from typing import Union

from grisera import (
    LifeActivityIn,
    LifeActivityOut,
    LifeActivitiesOut,
    BasicLifeActivityOut,
)
from grisera import LifeActivityService
from mongo_service.collection_mapping import Collections
from mongo_service.service_mixins import GenericMongoServiceMixin
from grisera import (
    ObservableInformationService,
)


class LifeActivityServiceMongoDB(LifeActivityService, GenericMongoServiceMixin):
    """
    Object to handle logic of life activity requests

    Attributes:
        observable_information_service (ObservableInformationService): Service used to add related Observable Information
        model_out_class (Type[BaseModel]): Out class of the model, used by GenericMongoServiceMixin
    """

    def __init__(self):
        super().__init__()
        self.model_out_class = LifeActivityOut
        self.observable_information_service: ObservableInformationService = None

    def save_life_activity(self, life_activity: LifeActivityIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new life activity. This method uses mixin create implementation.

        Args:
            life_activity (LifeActivityIn): Life activity to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as life activity object
        """
        return self.create(life_activity, dataset_id)

    def get_life_activities(self, dataset_id: Union[int, str]):
        """
        Send request to mongo api to get all life activities. This method uses mixin create implementation.

        Args:
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as list of life activity objects
        """
        result_dict = self.get_multiple(dataset_id=dataset_id)
        results = [BasicLifeActivityOut(**result) for result in result_dict]
        return LifeActivitiesOut(life_activities=results)

    def get_life_activity(
        self, life_activity_id: Union[int, str], dataset_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given life activity. This method uses mixin create implementation.

        Args:
            life_activity_id (int | str): identity of life activity
            dataset_id (int | str): name of dataset
            depth: (int): specifies how many related entities will be traversed to create the response
            source (str): internal argument for mongo services, used to tell the direction of model fetching.

        Returns:
            Result of request as life activity object
        """
        return self.get_single(life_activity_id, dataset_id, depth, source)

    def _add_related_documents(self, life_activity: dict, dataset_id: Union[int, str], depth: int, source: str):
        if source != Collections.OBSERVABLE_INFORMATION and depth > 0:
            life_activity[
                "observable_informations"
            ] = self.observable_information_service.get_multiple(
                dataset_id,
                {"life_activity_id": life_activity["id"]},
                depth=depth - 1,
                source=Collections.LIFE_ACTIVITY,
            )
