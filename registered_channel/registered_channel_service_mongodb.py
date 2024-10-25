from typing import Union

from mongo_service.collection_mapping import Collections
from mongo_service.service_mixins import (
    GenericMongoServiceMixin,
)
from mongo_service import MongoApiService
from grisera import RegisteredChannelService
from grisera import (
    RegisteredChannelOut,
    RegisteredChannelIn,
    BasicRegisteredChannelOut,
    RegisteredChannelsOut,
)
from grisera import NotFoundByIdModel


class RegisteredChannelServiceMongoDB(
    RegisteredChannelService, GenericMongoServiceMixin
):
    """
    Object to handle logic of registered channels requests

    Attributes:
    mongo_api_service (MongoApiService): Service used to communicate with Mongo API
    channel_service (ChannelServiceMongoDB): Service to send channel requests
    registered_data_service (RegisteredDataServiceMongoDB): Service to send registered data requests
    recording_service (RecordingServiceMongoDB): Service to send recording requests
    model_out_class (Type[BaseModel]): Out class of the model, used by GenericMongoServiceMixin
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.model_out_class = RegisteredChannelOut
        self.channel_service = None
        self.registered_data_service = None
        self.recording_service = None

    def save_registered_channel(self, registered_channel: RegisteredChannelIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new registered channel. This method uses mixin create implementation.

        Args:
            registered_channel (RegisteredChannelIn): Registered channel to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as registered channel object
        """
        related_channel = self.channel_service.get_channel(
            registered_channel.channel_id,
            dataset_id
        )
        channel_exists = type(related_channel) is not NotFoundByIdModel
        if registered_channel.channel_id is not None and not channel_exists:
            return RegisteredChannelOut(
                errors={"errors": "given channel does not exist"}
            )

        related_rd = self.registered_data_service.get_registered_data(
            registered_channel.registered_data_id,
            dataset_id
        )
        rd_exists = type(related_rd) is not NotFoundByIdModel
        if registered_channel.registered_data_id is not None and not rd_exists:
            return RegisteredChannelOut(
                errors={"errors": "given registered data does not exist"}
            )

        return self.create(registered_channel, dataset_id)

    def get_registered_channels(self, dataset_id: Union[int, str], query: dict = {}):
        """
        Send request to mongo api to get registered channels. This method uses mixin get implementation.

        Args:
            query (dict): Query for mongo request. Gets all registered channels by default.
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as list of registered channels objects
        """
        results_dict = self.get_multiple(dataset_id, query)
        results = [BasicRegisteredChannelOut(**result) for result in results_dict]
        return RegisteredChannelsOut(registered_channels=results)

    def get_registered_channel(
        self, registered_channel_id: Union[str, int], dataset_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given registered channel. This method uses mixin get implementation.

        Args:
            registered_channel_id (Union[str, int]): Id of registered channel
            dataset_id (int | str): name of dataset
            depth (int): this attribute specifies how many models will be traversed to create the response.
                         for depth=0, only no further models will be traversed.
            source (str): internal argument for mongo services, used to tell the direction of model fetching.
                          i.e. if for this service, if source="recording", it means that this method was invoked
                          from recording service, so recording model will not be fetched, as it is already in response.

        Returns:
            Result of request as registered channel object
        """
        return self.get_single(registered_channel_id, dataset_id, depth, source)

    def update_registered_channel_relationships(
        self,
        registered_channel_id: Union[str, int],
        updated_registered_channel: RegisteredChannelIn,
        dataset_id: Union[int, str],
    ):
        """
        Send request to mongo api to update given registered channel

        Args:
            registered_channel_id (Union[str, int]): Id of registered channel
            updated_registered_channel (RegisteredChannelIn): Document to update
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as registered channel object
        """
        existing_registered_channel = self.get_registered_channel(registered_channel_id, dataset_id)

        if type(existing_registered_channel) is NotFoundByIdModel:
            return existing_registered_channel

        if updated_registered_channel.channel_id is not None:
            related_channel = self.channel_service.get_channel(
                updated_registered_channel.channel_id,
                dataset_id
            )
            related_channel_exists = type(related_channel) is not NotFoundByIdModel
            if not related_channel_exists:
                return related_channel
        else:
            updated_registered_channel.channel_id = (
                existing_registered_channel.channel.getattr("id", None)
            )

        if updated_registered_channel.registered_data_id is not None:
            related_registered_channel = (
                self.registered_data_service.get_registered_data(
                    updated_registered_channel.registered_data_id,
                    dataset_id
                )
            )
            related_registered_channel_exists = (
                type(related_registered_channel) is not NotFoundByIdModel
            )
            if not related_registered_channel_exists:
                return related_registered_channel
        else:
            updated_registered_channel.registered_data_id = (
                existing_registered_channel.registered_data.getattr("id", None)
            )

        self.mongo_api_service.update_document(
            registered_channel_id,
            updated_registered_channel,
            dataset_id,
        )
        return self.get_registered_channel(registered_channel_id, dataset_id)

    def delete_registered_channel(self, registered_channel_id: Union[str, int], dataset_id: Union[int, str]):
        """
        Send request to mongo api to delete given registered channel. This method uses mixin delete implementation.

        Args:
            registered_channel_id (Union[str, int]): Id of registered channel
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as registered channel object
        """
        return self.delete(registered_channel_id, dataset_id)

    def _add_related_documents(self, registered_channel: dict, dataset_id: Union[int, str], depth: int, source: str):
        if depth > 0:
            self._add_related_recordings(registered_channel, dataset_id, depth, source)
            self._add_related_channel(registered_channel, dataset_id, depth, source)
            self._add_related_registered_data(registered_channel, dataset_id, depth, source)

    def _add_related_recordings(
        self, registered_channel: dict, dataset_id: Union[int, str], depth: int, source: str
    ):
        if source != Collections.RECORDING:
            registered_channel["recordings"] = self.recording_service.get_multiple(
                dataset_id,
                {"registered_channel_id": registered_channel["id"]},
                depth=depth - 1,
                source=Collections.REGISTERED_CHANNEL,
            )

    def _add_related_channel(self, registered_channel: dict, dataset_id: Union[int, str], depth: int, source: str):
        has_related_channel = registered_channel["channel_id"] is not None
        if source != Collections.CHANNEL and has_related_channel:
            registered_channel["channel"] = self.channel_service.get_single_dict(
                registered_channel["channel_id"],
                dataset_id,
                depth=depth - 1,
                source=Collections.REGISTERED_CHANNEL,
            )

    def _add_related_registered_data(
        self, registered_channel: dict, dataset_id: Union[int, str], depth: int, source: str
    ):
        has_related_rd = registered_channel["registered_data_id"] is not None
        if source != Collections.REGISTERED_DATA and has_related_rd:
            registered_channel[
                "registered_data"
            ] = self.registered_data_service.get_single_dict(
                registered_channel["registered_data_id"],
                dataset_id,
                depth=depth - 1,
                source=Collections.REGISTERED_CHANNEL,
            )
