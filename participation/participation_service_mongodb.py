from typing import Union

from grisera import ActivityExecutionService
from mongo_service.collection_mapping import Collections
from mongo_service import MongoApiService
from mongo_service.service_mixins import GenericMongoServiceMixin
from grisera import ParticipantStateService
from grisera import (
    ParticipationIn,
    ParticipationOut,
    ParticipationsOut,
    BasicParticipationOut,
)
from grisera import NotFoundByIdModel
from grisera import ParticipationService
from grisera import RecordingService


class ParticipationServiceMongoDB(ParticipationService, GenericMongoServiceMixin):
    """
    Object to handle logic of participation requests

    Attributes:
    mongo_api_service (MongoApiService): Service used to communicate with Mongo API
    activity_execution_service (ActivityExecutionService): Service to send activity execution requests
    participant_state_service (ParticipantStateService): Service to send participant state requests
    model_out_class (Type[BaseModel]): Out class of the model, used by GenericMongoServiceMixin
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.model_out_class = ParticipationOut
        self.activity_execution_service: ActivityExecutionService = None
        self.participant_state_service: ParticipantStateService = None
        self.recording_service: RecordingService = None

    def save_participation(self, participation: ParticipationIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new participation

        Args:
            participation (ParticipationIn): Participation to be added

        Returns:
            Result of request as participation object
        """

        if not self._check_related_activity_execution(
            participation.activity_execution_id, dataset_id
        ):
            return ParticipationOut(
                errors={"errors": "given activity execution does not exist"}
            )

        if not self._check_related_participant_state(
            participation.participant_state_id, dataset_id
        ):
            return ParticipationOut(
                errors={"errors": "given participant state does not exist"}
            )

        return self.create(participation, dataset_id)

    def get_participations(self, dataset_id: Union[int, str], query: dict = {}):
        """
        Send request to mongo api to get participations
        Returns:
            Result of request as list of participation objects
        """
        results_dict = self.get_multiple(dataset_id, query)
        results = [BasicParticipationOut(**result) for result in results_dict]
        return ParticipationsOut(participations=results)

    def get_participation(
        self, participation_id: Union[int, str], dataset_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given participation
        Args:
            participation_id (int | str): identity of participation
            depth: (int): specifies how many related entities will be traversed to create the response
            source (str): internal argument for mongo services, used to tell the direction of model fetching.

        Returns:
            Result of request as participation object
        """
        return self.get_single(participation_id, dataset_id, depth, source)

    def delete_participation(self, participation_id: Union[int, str], dataset_id: Union[int, str]):
        """
        Send request to mongo api to delete given participation
        Args:
            participation_id (int | str): identity of participation
        Returns:
            Result of request as participation object
        """
        return self.delete(participation_id, dataset_id)

    def update_participation_relationships(
        self, participation_id: Union[int, str], participation: ParticipationIn, dataset_id: Union[int, str]
    ):
        """
        Send request to mongo api to update given participation relationships
        Args:
            participation_id (int | str): identity of participation
            participation (ParticipationIn): Relationships to update
        Returns:
            Result of request as participation object
        """
        existing_participation = self.get_participation(participation_id, dataset_id)

        if not self._check_related_participant_state(
            participation.participant_state_id, dataset_id
        ):
            return ParticipationOut(
                errors={"errors": "given participant state does not exist"}
            )

        if not self._check_related_activity_execution(
            participation.activity_execution_id, dataset_id
        ):
            return ParticipationOut(
                errors={"errors": "given activity execution does not exist"}
            )

        existing_participation.activity_execution_id = (
            participation.activity_execution_id
        )
        existing_participation.participant_state_id = participation.participant_state_id
        self.update(participation_id, existing_participation, dataset_id)

        return self.get_participation(participation_id, dataset_id)

    def _check_related_participant_state(self, participant_state_id, dataset_id: Union[int, str]):
        related_participant_state = (
            self.participant_state_service.get_participant_state(participant_state_id, dataset_id)
        )
        participant_state_exists = type(related_participant_state) is not NotFoundByIdModel
        return participant_state_id is None or participant_state_exists

    def _check_related_activity_execution(self, activity_execution_id, dataset_id: Union[int, str]):
        related_activity_execution = (
            self.activity_execution_service.get_activity_execution(
                activity_execution_id,
                dataset_id
            )
        )
        activity_execution_exists = type(related_activity_execution) is not NotFoundByIdModel
        return activity_execution_id is None or activity_execution_exists

    def _add_related_documents(self, participation: dict, dataset_id: Union[int, str], depth: int, source: str):
        if depth > 0:
            self._add_related_recordings(participation, dataset_id, depth, source)
            self._add_related_participant_state(participation, dataset_id, depth, source)
            self._add_related_activity_executions(participation, dataset_id, depth, source)

    def _add_related_recordings(self, participation: dict, dataset_id: Union[int, str], depth: int, source: str):
        if source != Collections.RECORDING:
            participation["recordings"] = self.recording_service.get_multiple(
                dataset_id,
                {"participation_id": participation["id"]},
                depth=depth - 1,
                source=Collections.PARTICIPATION,
            )

    def _add_related_participant_state(
        self, participation: dict, dataset_id: Union[int, str], depth: int, source: str
    ):
        has_related_ps = participation["participant_state_id"] is not None
        if source != Collections.PARTICIPANT_STATE and has_related_ps:
            participation[
                "participant_state"
            ] = self.participant_state_service.get_single_dict(
                participation["participant_state_id"],
                dataset_id,
                depth=depth - 1,
                source=Collections.PARTICIPATION,
            )

    def _add_related_activity_executions(
        self, participation: dict, dataset_id: Union[int, str], depth: int, source: str
    ):
        has_related_ae = participation["activity_execution_id"] is not None
        if source != Collections.ACTIVITY_EXECUTION and source != Collections.EXPERIMENT and has_related_ae:
            participation[
                "activity_execution"
            ] = self.activity_execution_service.get_single_dict(
                participation["activity_execution_id"],
                dataset_id,
                depth=depth - 1,
                source=Collections.ACTIVITY_EXECUTION,
            )
