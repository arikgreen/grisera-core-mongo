from typing import Union

from bson import ObjectId

from grisera import NotFoundByIdModel
from mongo_service import MongoApiService
from mongo_service.collection_mapping import Collections
from mongo_service.service_mixins import GenericMongoServiceMixin
from grisera import (
    ParticipantIn,
    ParticipantsOut,
    BasicParticipantOut,
    ParticipantOut,
)
from grisera import ParticipantService
from grisera import (
    BasicParticipantStateOut,
    ParticipantStateIn,
    ParticipantStateOut,
)
from grisera import ParticipantStateService

from participant.participant_model import BasicParticipantOutToMongo


class ParticipantServiceMongoDB(ParticipantService, GenericMongoServiceMixin):
    """
    Object to handle logic of participants requests. There are also participant state methods,
    as participant state documents are embedded within participants documents.

    Attributes:
    mongo_api_service (MongoApiService): Service used to communicate with Mongo API
    participant_state_service (ParticipantStateService): Service to send participant state requests
    model_out_class (Type[BaseModel]): Out class of the model, used by GenericMongoServiceMixin
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.model_out_class = ParticipantOut
        self.participant_state_service: ParticipantStateService = None

    def save_participant(self, participant: ParticipantIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new participant

        Args:
            participant (ParticipantIn): Participant to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as participant object
        """
        return self.create(participant, dataset_id)

    def get_participants(self, dataset_id: Union[int, str], query: dict = {}):
        """
        Send request to mongo api to get participants

        Args:
            dataset_id (int | str): name of dataset
        Returns:
            Result of request as list of participants objects
        """
        results_dict = self.get_multiple(dataset_id, query)
        results = [BasicParticipantOut(**result) for result in results_dict]
        return ParticipantsOut(participants=results)

    def get_participant(
        self, participant_id: Union[int, str], dataset_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given participant

        Args:
            participant_id (int | str): identity of participant
            dataset_id (int | str): name of dataset
            depth (int): this attribute specifies how many models will be traversed to create the response.
                         for depth=0, only no further models will be traversed.
            source (str): internal argument for mongo services, used to tell the direction of model fetching.

        Returns:
            Result of request as participant object
        """
        return self.get_single(participant_id, dataset_id, depth, source)

    def delete_participant(self, participant_id: Union[int, str], dataset_id: Union[int, str]):
        """
        Send request to mongo api to delete given participant

        Args:
            participant_id (int): Id of participant
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as participant object
        """
        return self.delete(participant_id, dataset_id)

    def update_participant(
        self, participant_id: Union[int, str], participant: ParticipantIn, dataset_id: Union[int, str]
    ):
        """
        Send request to mongo api to update given participant

        Args:
            participant_id (int | str): Id of participant
            participant (ParticipantIn): Properties to update
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as participant object
        """
        return self.update(participant_id, participant, dataset_id)

    def add_participant_state(self, participant_state: ParticipantStateIn, dataset_id: Union[int, str]):
        participant_state_dict = participant_state.dict()
        participant_state_dict["id"] = str(ObjectId())
        participant_state = BasicParticipantStateOut(**participant_state_dict)

        participant_id = participant_state.participant_id
        participant = self.get_single_dict(participant_id, dataset_id)
        participant_states = participant.get(Collections.PARTICIPANT_STATE, [])
        if participant_states is None:
            participant_states = []
        participant_states.append(participant_state)
        participant[Collections.PARTICIPANT_STATE] = participant_states

        self.update(participant_id, BasicParticipantOutToMongo(**participant), dataset_id)
        return BasicParticipantStateOut(**participant_state_dict)

    def update_participant_state(
        self,
        participant_state_id: Union[int, str],
        participant_state_dict: dict,
        dataset_id: Union[int, str],
    ):
        """
        Edit participant state in participant. Participant state is embedded in related participant.

        Args:
            participant_state_id (Union[int, str]): id of participant state that is to be updated
            participant_state_dict (dict): new version of participant state
            dataset_id (int | str): name of dataset

        Returns:
            Updated participant state
        """
        participant_id = participant_state_dict["participant_id"]
        participant = self.get_single_dict(participant_id, dataset_id)
        if type(participant) is NotFoundByIdModel:
            return NotFoundByIdModel(
                id=participant_state_id,
                errors={
                    "errors": "participant related to given participant state not found"
                },
            )

        to_update_index = self._get_participant_state_index_from_participant(
            participant, participant_state_id
        )
        if to_update_index is None:
            return NotFoundByIdModel(
                id=participant_state_id,
                errors={"errors": "participant state not found"},
            )
        participant_states = participant[Collections.PARTICIPANT_STATE]
        participant_states[to_update_index] = BasicParticipantStateOut(**participant_state_dict)
        self.update(participant_id, BasicParticipantOutToMongo(**participant), dataset_id)
        return ParticipantStateOut(**participant_state_dict)

    def remove_participant_state(self, participant_state: ParticipantStateOut, dataset_id: Union[int, str]):
        """
        Remove participant state from participant. Participant state is embedded in related participant.

        Args:
            participant_state (ParticipantStateOut): participant state to remove
            dataset_id (int | str): name of dataset

        Returns:
            Removed participant state
        """
        participant_id = participant_state.participant_id
        participant = self.get_single_dict(participant_id, dataset_id)
        if type(participant) is NotFoundByIdModel:
            return NotFoundByIdModel(
                id=participant_state.id,
                errors={
                    "errors": "participant related to given participant state not found"
                },
            )

        to_remove_index = self._get_participant_state_index_from_participant(
            participant, participant_state.id
        )
        if to_remove_index is None:
            return NotFoundByIdModel(
                id=participant_state.id,
                errors={"errors": "participant state not found"},
            )
        del participant[Collections.PARTICIPANT_STATE][to_remove_index]

        self.update(participant_id, BasicParticipantOutToMongo(**participant), dataset_id)
        return participant_state

    def _get_participant_state_index_from_participant(
        self, participant_dict: dict, participant_state_id: Union[str, int]
    ):
        """
        Participant state is embedded within participant model
        """
        participant_states = participant_dict[Collections.PARTICIPANT_STATE]
        return next(
            (
                i
                for i, ps in enumerate(participant_states)
                if ObjectId(ps["id"]) == ObjectId(participant_state_id)
            ),
            None,
        )

    def _add_related_documents(self, participant: dict, dataset_id: Union[int, str], depth: int, source: str):
        if depth > 0:
            self._add_related_partcipant_states(participant, dataset_id, depth, source)

    def _add_related_partcipant_states(
        self, participant: dict, dataset_id: Union[int, str], depth: int, source: str
    ):
        """
        Partcipant state is embedded within participant model
        """
        has_partcipant_states = participant[Collections.PARTICIPANT_STATE] is not None
        if source != Collections.PARTICIPANT_STATE and has_partcipant_states:
            for ps in participant[Collections.PARTICIPANT_STATE]:
                self.participant_state_service._add_related_documents(
                    ps, dataset_id, depth - 1, Collections.PARTICIPANT, participant
                )
