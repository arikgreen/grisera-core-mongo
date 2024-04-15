from typing import List, Union

from bson import ObjectId

from grisera import AppearanceService
from mongo_service.collection_mapping import Collections
from mongo_service.service_mixins import GenericMongoServiceMixin
from grisera import ParticipantService
from grisera import ParticipantStateService
from grisera import (
    ParticipantStatePropertyIn,
    BasicParticipantStateOut,
    ParticipantStatesOut,
    ParticipantStateOut,
    ParticipantStateIn,
    ParticipantStateRelationIn,
)
from grisera import NotFoundByIdModel
from grisera import ParticipationService
from grisera import PersonalityService


class ParticipantStateServiceMongoDB(ParticipantStateService, GenericMongoServiceMixin):
    """
    Object to handle logic of participant state requests

    Attributes:
        graph_api_service (GraphApiService): Service used to communicate with Graph API
        participant_service (ParticipantService): Service to manage participant models
        appearance_service (AppearanceService): Service to manage appearance models
        personality_service (PersonalityService): Service to manage personality models
        model_out_class (Type[BaseModel]): Out class of the model, used by GenericMongoServiceMixin
    """

    def __init__(self):
        super().__init__()
        self.model_out_class = ParticipantStateOut
        self.participant_service: ParticipantService = None
        self.appearance_service: AppearanceService = None
        self.personality_service: PersonalityService = None
        self.participation_service: ParticipationService = None

    def save_participant_state(self, participant_state: ParticipantStateIn):
        """
        Send request to mongo api to create new participant state

        Args:
            participant_state (ParticipantStateIn): Participant state to be added

        Returns:
            Result of request as participant state object
        """
        is_correct, error = self._check_related_fields(participant_state)
        if not is_correct:
            return error

        basic_ps = self.participant_service.add_participant_state(participant_state)
        return ParticipantStateOut(**basic_ps.dict())

    def get_multiple(
        self, query: dict = {}, depth: int = 0, source: str = "", *args, **kwargs
    ):
        """
        Get multiple participant states based on query. Query has to be adjusted, as participant states
        documents are embedded within participant documents.
        """
        participant_query = {
            f"{Collections.PARTICIPANT_STATE}.{field}": value
            for field, value in query.items()
        }
        participant_results = self.participant_service.get_multiple(
            participant_query,
            depth=depth - 1,
            source=Collections.PARTICIPANT_STATE,
            projection=self._get_participant_projection(query),
        )

        result = []
        for participant_result in participant_results:
            participant_states = participant_result["participant_states"]
            del participant_result["participant_states"]
            for participant_state in participant_states:
                self._add_related_documents(
                    participant_state,
                    depth - 1,
                    source,
                    participant_results,
                )
            result += participant_states

        return result

    def get_participant_states(self):
        """
        Send request to mongo api to get all participant states.
        """
        participant_state_dicts = self.get_multiple()
        results = [
            BasicParticipantStateOut(**result) for result in participant_state_dicts
        ]
        return ParticipantStatesOut(observable_informations=results)

    def get_single_dict(
        self, id: Union[str, int], depth: int = 0, source: str = "", *args, **kwargs
    ):
        """
        Get participant state dict. Participant state is fetched from its participant.
        """
        participant_state_object_id = ObjectId(id)
        participant_result = self.participant_service.get_multiple(
            {f"{Collections.PARTICIPANT_STATE}.id": participant_state_object_id},
            depth=depth - 1,
            source=Collections.PARTICIPANT_STATE,
            projection=self._get_participant_projection(
                {"id": participant_state_object_id}
            ),
        )
        if (
            len(participant_result) == 0
            or len(participant_result[0][Collections.PARTICIPANT_STATE]) == 0
        ):
            return NotFoundByIdModel(
                id=id,
                errors={"errors": "participant state not found"},
            )
        related_participant = participant_result[0]
        participant_state_dict = related_participant[Collections.PARTICIPANT_STATE][0]
        del related_participant[Collections.PARTICIPANT_STATE]
        self._add_related_documents(
            participant_state_dict, depth, source, related_participant
        )
        return participant_state_dict

    def get_single(
        self, id: Union[str, int], depth: int = 0, source: str = "", *args, **kwargs
    ):
        """
        Get single participation state object.
        """
        result = self.get_single_dict(id, depth, source, *args, **kwargs)
        if type(result) is NotFoundByIdModel:
            return result
        return ParticipantStateOut(**result)

    def get_participant_state(
        self, id: Union[str, int], depth: int = 0, source: str = "", *args, **kwargs
    ):
        """
        Get single participation state object.
        """
        return self.get_single(id, depth, source, *args, **kwargs)

    def delete_participant_state(self, participant_state_id: Union[int, str]):
        """
        Send request to mongo api to delete given participant state

        Args:
            participant_state_id (int | str): Id of participant state

        Returns:
            Result of request as participant state object
        """
        participant_state = self.get_participant_state(participant_state_id)
        if type(participant_state) is NotFoundByIdModel:
            return NotFoundByIdModel(
                id=participant_state_id,
                errors={"errors": "participant state not found"},
            )
        return self.recording_service.remove_participant_state(participant_state)

    def update_participant_state(
        self,
        participant_state_id: Union[int, str],
        participant_state: ParticipantStatePropertyIn,
    ):
        """
        Take existing participation state and change property fields in them.

        Args:
            participant_state_id (int): Id of participant state
            participant_state (ParticipantStatePropertyIn): Properties to update

        Returns:
            Result of request as participant state object
        """
        existing_participant_state = self.get_participant_state(participant_state_id)
        new_participant_state_dict = participant_state.dict()
        for field in new_participant_state_dict:
            new_participant_state_dict[field] = existing_participant_state[field]
        return self.participant_service.update_participant_state(
            participant_state_id, new_participant_state_dict
        )

    def update_participant_state_relationships(
        self,
        participant_state_id: Union[int, str],
        participant_state: ParticipantStateRelationIn,
    ):
        """
        Take existing participation state and change relationship fields in them.

        Args:
            participant_state_id (int | str): identity of participant state
            participant_state (ParticipantStateRelationIn): Relationships to update

        Returns:
            Result of request as participant state object
        """
        existing_participant_state = self.get_participant_state(participant_state_id)
        new_participant_state_dict = participant_state.dict()
        for field in new_participant_state_dict:
            new_participant_state_dict[field] = existing_participant_state[field]
        return self.participant_service.update_participant_state(
            participant_state_id, new_participant_state_dict
        )

    def _check_related_fields(self, participant: ParticipantStateRelationIn):
        if not self._check_related_appearances(participant.appearance_ids):
            return False, ParticipantStateOut(
                errors={"errors": "one of given appearances does not exist"}
            )

        if not self._check_related_personalities(participant.personality_ids):
            return False, ParticipantStateOut(
                errors={"errors": "one of given personalities does not exist"}
            )

        if not self._check_related_participant(participant.participant_id):
            return False, ParticipantStateOut(
                errors={"errors": "given participant does not exist"}
            )

        return True, None

    def _check_related_participant(self, participant_id: Union[str, int]):
        related_participant = self.participant_service.get_participant(participant_id)
        related_participant_exists = related_participant is not NotFoundByIdModel
        return participant_id is None or related_participant_exists

    def _check_related_personalities(self, personality_ids: List[Union[str, int]]):
        if personality_ids is None:
            return True
        existing_personalities = self.personality_service.get_multiple(
            query={"id": self.mongo_api_service.get_id_in_query(personality_ids)},
        )
        all_given_personalities_extist = len(existing_personalities) == len(
            personality_ids
        )
        return all_given_personalities_extist

    def _check_related_appearances(self, appearance_ids: List[Union[str, int]]):
        if appearance_ids is None:
            return True
        existing_appearances = self.appearance_service.get_multiple(
            query={"id": self.mongo_api_service.get_id_in_query(appearance_ids)},
        )
        all_given_appearances_extist = len(existing_appearances) == len(appearance_ids)
        return all_given_appearances_extist

    def _add_related_documents(
        self,
        participant_state: dict,
        depth: int,
        source: str,
        participant: dict,
    ):
        """Participant is taken from previous get query"""
        if depth > 0:
            self._add_related_personalities(participant_state, depth, source)
            self._add_related_appearances(participant_state, depth, source)
            self._add_related_participations(participant_state, depth, source)
            self._add_related_participant(participant_state, depth, source, participant)

    def _add_related_participant(
        self, participant_state: dict, depth: int, source: str, participant: dict
    ):
        """Recording has already been added related documents"""
        if source != Collections.PARTICIPANT:
            participant_state["participant"] = participant

    def _add_related_participations(
        self, participant_state: dict, depth: int, source: str
    ):
        if source != Collections.PARTICIPATION:
            participant_state[
                "participations"
            ] = self.participation_service.get_multiple(
                {"participant_state_id": participant_state["id"]},
                depth=depth - 1,
                source=Collections.PARTICIPANT_STATE,
            )

    def _add_related_appearances(
        self, participant_state: dict, depth: int, source: str
    ):
        if participant_state["appearance_ids"] is None:
            return
        if source != Collections.APPEARANCE:
            participant_state["appearances"] = self.appearance_service.get_multiple(
                {
                    "id": self.mongo_api_service.get_id_in_query(
                        participant_state["appearance_ids"]
                    )
                },
                depth=depth - 1,
                source=Collections.PARTICIPANT_STATE,
            )

    def _add_related_personalities(
        self, participant_state: dict, depth: int, source: str
    ):
        if participant_state["personality_ids"] is None:
            return
        if source != Collections.PERSONALITY:
            participant_state["personalities"] = self.personality_service.get_multiple(
                {
                    "id": self.mongo_api_service.get_id_in_query(
                        participant_state["personality_ids"]
                    )
                },
                depth=depth - 1,
                source=Collections.PARTICIPANT_STATE,
            )

    @staticmethod
    def _get_participant_projection(query):
        return {
            "participant_states": {"$elemMatch": query},
            "participant_states": 1,
            "additional_properties": 1,
            "name": 1,
            "date_of_birth": 1,
            "sex": 1,
            "disorder": 1,
        }
