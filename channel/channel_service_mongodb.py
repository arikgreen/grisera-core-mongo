from typing import Union, Type
from grisera import ChannelService
from grisera import ChannelIn, ChannelOut, ChannelsOut, BasicChannelOut
from mongo_service.collection_mapping import Collections
from mongo_service.service_mixins import GenericMongoServiceMixin


class ChannelServiceMongoDB(ChannelService, GenericMongoServiceMixin):
    """
    Object to handle logic of channel requests

    Attributes:
    registered_channel_service (RegisteredChannelService): Service to send registered channel requests
    model_out_class (Type[BaseModel]): Out class of the model, used by GenericMongoServiceMixin
    """

    def __init__(self):
        super().__init__()
        self.model_out_class = ChannelOut
        self.registered_channel_service = None

    def save_channel(self, channel: ChannelIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new channel. This method uses mixin create implementation.

        Args:
            channel (ChannelIn): Channel to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as channel object
        """
        return self.create(channel, dataset_id)

    def get_channels(self, dataset_id: Union[int, str]):
        """
        Send request to mongo api to get all channels. This method uses mixin get implementation.

        Args:
            dataset_id (int | str): name of dataset
        Returns:
            Result of request as ChannelsOut object
        """
        results_dict = self.get_multiple(dataset_id)
        results = [BasicChannelOut(**result) for result in results_dict]
        return ChannelsOut(channels=results)

    def get_channel(
            self, channel_id: Union[str, int], dataset_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given channel with related models. This method uses mixin get implementation.

        Args:
            channel_id (Union[str, int]): Id of channel
            dataset_id (int | str): name of dataset
            depth (int): this attribute specifies how many models will be traversed to create the response.
                         for depth=0, only no further models will be traversed.
            source (str): internal argument for mongo services, used to tell the direction of model fetching.

    Returns:
        Result of request as channel out class
    """
        return self.get_single(channel_id, dataset_id, depth, source)

    def _add_related_documents(self, channel: dict, dataset_id: Union[int, str], depth: int, source: str):
        if source != Collections.REGISTERED_CHANNEL and depth > 0:
            channel[
                "registered_channels"
            ] = self.registered_channel_service.get_multiple(
                dataset_id,
                {"channel_id": channel["id"]},
                depth=depth - 1,
                source=Collections.CHANNEL,
            )
