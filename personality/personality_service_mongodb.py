from typing import Union

from grisera import NotFoundByIdModel
from mongo_service.collection_mapping import Collections
from mongo_service.mongo_api_service import MongoApiService
from grisera import ParticipantStateService
from grisera import (
    PersonalityBigFiveIn,
    PersonalityBigFiveOut,
    PersonalityPanasIn,
    PersonalityPanasOut,
    BasicPersonalityBigFiveOut,
    BasicPersonalityPanasOut,
    PersonalitiesOut,
)
from grisera import PersonalityService

from mongo_service.service_mixins import GenericMongoServiceMixin


class PersonalityServiceMongoDB(PersonalityService, GenericMongoServiceMixin):
    """
    Object to handle logic of personality requests
    """

    def __init__(self):
        self.mongo_api_service = MongoApiService()
        self.participant_state_service: ParticipantStateService = None
        self.model_out_class = PersonalityBigFiveOut

    def save_personality_big_five(self, personality: PersonalityBigFiveIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new personality big five model

        Args:
            personality (PersonalityBigFiveIn): Personality big five to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as personality big five object
        """

        if (
            not 0 <= personality.agreeableness <= 1
            or not 0 <= personality.conscientiousness <= 1
            or not 0 <= personality.extroversion <= 1
            or not 0 <= personality.neuroticism <= 1
            or not 0 <= personality.openess <= 1
        ):
            return PersonalityBigFiveOut(
                **personality.dict(), errors="Value not between 0 and 1"
            )
        self.model_out_class = PersonalityBigFiveOut

        return self.create(personality, dataset_id)

    def save_personality_panas(self, personality: PersonalityPanasIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new personality panas model

        Args:
            personality (PersonalityPanasIn): Personality to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as personality panas object
        """
        if (
            not 0 <= personality.negative_affect <= 1
            or not 0 <= personality.positive_affect <= 1
        ):
            return PersonalityPanasOut(
                **personality.dict(), errors="Value not between 0 and 1"
            )
        self.model_out_class = PersonalityPanasOut

        return self.create(personality, dataset_id)

    def get_single(self, id: Union[str, int], dataset_id: Union[int, str], depth: int = 0, source: str = ""):
        personality = self.get_single_dict(id, dataset_id, depth, source)
        if type(personality) is NotFoundByIdModel:
            return personality
        return (
            PersonalityPanasOut(**personality)
            if "negative_affect" in personality.keys()
            else PersonalityBigFiveOut(**personality)
        )

    def get_personality(
        self, personality_id: Union[int, str], dataset_id: Union[int, str], depth: int = 0, source: str = ""
    ):
        """
        Send request to mongo api to get given personality

        Args:
            personality_id (int | str): identity of personality
            dataset_id (int | str): name of dataset
            depth: (int): specifies how many related entities will be traversed to create the response
            source: Helper arguments that specifies direction of collection traversion


        Returns:
            Result of request as personality object
        """
        return self.get_single(personality_id, dataset_id, depth, source)

    def get_personalities(self, dataset_id: Union[int, str], query: dict = {}):
        """
        Send request to mongo api to get personalities

        Args:
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as list of personalities objects
        """
        results_dict = self.get_multiple(dataset_id, query)

        personalities = []

        for personality_dict in results_dict:
            personality = (
                BasicPersonalityPanasOut(**personality_dict)
                if "negative_affect" in personality_dict.keys()
                else BasicPersonalityBigFiveOut(**personality_dict)
            )
            personalities.append(personality)

        return PersonalitiesOut(personalities=personalities)

    def delete_personality(self, personality_id: Union[int, str], dataset_id: Union[int, str]):
        """
        Send request to mongo api to delete given personality

        Args:
            personality_id (int | str): identity of personality
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as personality object
        """
        return self.delete(personality_id, dataset_id)

    def update_personality_big_five(
        self, personality_id: Union[int, str], personality: PersonalityBigFiveIn, dataset_id: Union[int, str]
    ):
        """
        Send request to mongo api to update given personality big five model

        Args:
            personality_id (int | str): identity of personality
            personality (PersonalityBigFiveIn): Properties to update
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as personality object
        """
        if (
            not 0 <= personality.agreeableness <= 1
            or not 0 <= personality.conscientiousness <= 1
            or not 0 <= personality.extroversion <= 1
            or not 0 <= personality.neuroticism <= 1
            or not 0 <= personality.openess <= 1
        ):
            return BasicPersonalityBigFiveOut(
                **personality.dict(), errors="Value not between 0 and 1"
            )

        get_response = self.get_personality(personality_id, dataset_id)
        if type(get_response) is NotFoundByIdModel:
            return get_response
        if type(get_response) is PersonalityPanasOut:
            return NotFoundByIdModel(id=personality_id, errors="Node not found.")

        self.mongo_api_service.update_document(personality_id, personality, dataset_id)
        return self.get_personality(personality_id, dataset_id)

    def update_personality_panas(
        self, personality_id: Union[int, str], personality: PersonalityPanasIn, dataset_id: Union[int, str]
    ):
        """
        Send request to mongo api to update given personality panas model

        Args:
            personality_id (int | str): identity of personality
            personality (PersonalityPanasIn): Properties to update
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as personality object
        """
        if (
            not 0 <= personality.negative_affect <= 1
            or not 0 <= personality.positive_affect <= 1
        ):
            return BasicPersonalityPanasOut(
                **personality.dict(), errors="Value not between 0 and 1"
            )

        get_response = self.get_personality(personality_id, dataset_id)
        if type(get_response) is NotFoundByIdModel:
            return get_response
        if type(get_response) is PersonalityBigFiveOut:
            return NotFoundByIdModel(id=personality_id, errors="Node not found.")

        self.mongo_api_service.update_document(personality_id, personality, dataset_id)
        return self.get_personality(personality_id, dataset_id)

    def _add_related_documents(
        self,
        personality: dict,
        dataset_id: Union[int, str],
        depth: int,
        source: str,
    ):
        if depth > 0:
            self._add_participant_states(personality, dataset_id, depth, source)

    def _add_participant_states(self, personality: dict, dataset_id: Union[int, str], depth: int, source: str):
        if source != Collections.PARTICIPANT_STATE:
            query = {"personality_ids": personality["id"]}
            personality[
                "participant_states"
            ] = self.participant_state_service.get_multiple(
                dataset_id,
                query,
                depth=depth - 1,
                source=Collections.PERSONALITY,
            )
