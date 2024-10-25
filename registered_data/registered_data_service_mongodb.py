from typing import Union
from mongo_service.collection_mapping import Collections
from mongo_service.service_mixins import (
    GenericMongoServiceMixin,
)
from grisera import (
    RegisteredDataIn,
    RegisteredDataNodesOut,
    BasicRegisteredDataOut,
    RegisteredDataOut,
)
from grisera import RegisteredDataService


class RegisteredDataServiceMongoDB(RegisteredDataService, GenericMongoServiceMixin):
    """
    Object to handle logic of registered data requests
    registered_channel_service (RegisteredChannelService): Channel service for adding related channels
    model_out_class (Type[BaseModel]): Out class of the model, used by GenericMongoServiceMixin
    """

    def __init__(self):
        super().__init__()
        self.model_out_class = RegisteredDataOut
        self.registered_channel_service = None

    def save_registered_data(self, registered_data: RegisteredDataIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new registered data node. This method uses mixin create implementation.

        Args:
            registered_data (RegisteredDataIn): Registered data to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as registered data object
        """
        return self.create(registered_data, dataset_id)

    def get_registered_data_nodes(self, dataset_id: Union[int, str]):
        """
        Send request to mongo api to get all registered data nodes. This method uses mixin get implementation.

        Args:
            dataset_id (int | str): name of dataset
        Returns:
            Result of request as list of registered data objects
        """
        result_dict = self.get_multiple(dataset_id)
        results = [BasicRegisteredDataOut(**result) for result in result_dict]
        return RegisteredDataNodesOut(registered_data_nodes=results)

    def get_registered_data(
        self, registered_data_id: Union[str, int], dataset_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given registered data with related models. This method uses mixin get implementation.

        Args:
            registered_data_id (Union[str, int]): Id of registered data
            depth (int): this attribute specifies how many models will be traversed to create the response.
                         for depth=0, only no further models will be traversed.
            source (str): internal argument for mongo services, used to tell the direction of model fetching.
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as registered data dictionary
        """
        return self.get_single(registered_data_id, dataset_id, depth, source)

    def update_registered_data(
        self, registered_data_id: Union[str, int], registered_data: RegisteredDataIn,
                               dataset_id: Union[int, str]
    ):
        """
        Send request to mongo api to update given registered data. This method uses mixin update implementation.

        Args:
            registered_data_id (Union[str, int]): Id of registered data
            registered_data (RegisteredDataIn): Properties to update
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as registered data object
        """
        return self.update(registered_data_id, registered_data, dataset_id)

    def delete_registered_data(self, registered_data_id: Union[str, int],
                               dataset_id: Union[int, str]):
        """
        Send request to mongo api to delete given registered data. This method uses mixin delete implementation.

        Args:
            registered_data_id (Union[str, int]): Id of registered data
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as registered data object
        """
        return self.delete(registered_data_id, dataset_id)

    def _add_related_documents(self, registered_data: dict, dataset_id: Union[int, str], depth: int, source: str):
        if source != Collections.REGISTERED_CHANNEL and depth > 0:
            registered_data[
                "registered_channels"
            ] = self.registered_channel_service.get_multiple(
                dataset_id,
                {"registered_data_id": registered_data["id"]},
                depth=depth - 1,
                source=Collections.REGISTERED_DATA,
            )
