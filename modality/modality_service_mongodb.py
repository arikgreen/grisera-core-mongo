from typing import Union

from mongo_service.service_mixins import GenericMongoServiceMixin
from mongo_service.collection_mapping import Collections
from grisera import (
    ModalityIn,
    ModalityOut,
    ModalitiesOut,
    BasicModalityOut,
)
from grisera import ModalityService
from grisera import (
    ObservableInformationService,
)


class ModalityServiceMongoDB(ModalityService, GenericMongoServiceMixin):
    """
    Object to handle logic of modality requests

    Attributes:
        observable_information_service (ObservableInformationService): Service used to add related Observable Information
        model_out_class (Type[BaseModel]): Out class of the model, used by GenericMongoServiceMixin
    """

    def __init__(self):
        super().__init__()
        self.model_out_class = ModalityOut
        self.observable_information_service: ObservableInformationService = None

    def save_modality(self, modality: ModalityIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new modality. This method uses mixin create implementation.

        Args:
            modality (ModalityIn): Modality to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as modality object
        """
        return self.create(modality, dataset_id)

    def get_modalities(self, dataset_id: Union[int, str]):
        """
        Send request to mongo api to get all modalities. This method uses mixin create implementation.

        Args:
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as list of modality objects
        """
        result_dict = self.get_multiple(dataset_id)
        results = [BasicModalityOut(**result) for result in result_dict]
        return ModalitiesOut(modalities=results)

    def get_modality(
        self, modality_id: Union[int, str], dataset_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given modality. This method uses mixin create implementation.

        Args:
            depth: (int): specifies how many related entities will be traversed to create the response
            modality_id (int | str): identity of modality
            dataset_id (int | str): name of dataset
            source (str): internal argument for mongo services, used to tell the direction of model fetching.

        Returns:
            Result of request as modality object
        """
        return self.get_single(modality_id, dataset_id, depth, source)

    def _add_related_documents(self, modality: dict, dataset_id: Union[int, str], depth: int, source: str):
        if source != Collections.OBSERVABLE_INFORMATION and depth > 0:
            modality[
                "observable_informations"
            ] = self.observable_information_service.get_multiple(
                dataset_id,
                {"modality_id": modality["id"]},
                depth=depth - 1,
                source=Collections.MODALITY,
            )
