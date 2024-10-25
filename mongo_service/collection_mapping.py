from grisera import ActivityIn, DatasetIn
from grisera import (
    ActivityExecutionPropertyIn,
    ActivityExecutionRelationIn,
)
from grisera import (
    AppearanceOcclusionOut,
    AppearanceSomatotypeOut,
    AppearanceOcclusionIn,
    AppearanceSomatotypeIn,
)
from grisera import ArrangementIn
from grisera import ChannelIn
from grisera import ExperimentIn
from grisera import LifeActivityIn
from grisera import MeasurePropertyIn, MeasureRelationIn
from grisera import MeasureNameIn
from grisera import ModalityIn
from grisera import (
    ObservableInformationIn,
)
from grisera import ParticipantIn
from grisera import (
    ParticipantStatePropertyIn,
    ParticipantStateRelationIn,
)
from grisera import ParticipationIn, BasicParticipationOut
from grisera import (
    PersonalityBigFiveIn,
    PersonalityPanasIn,
)
from grisera import (
    RecordingPropertyIn,
    RecordingRelationIn,
)
from grisera import (
    RegisteredChannelIn,
    BasicRegisteredChannelOut,
)
from grisera import RegisteredDataIn
from grisera import (
    ScenarioIn,
    ScenarioOut,
)
from grisera import (
    TimeSeriesPropertyIn,
    TimeSeriesRelationIn,
)
from enum import Enum

"""
This module provides enum with collection names in mongodb to help avoiding 
possible errors with typos in collection names strings.

It also provides mapping of model classes to collection names. It is useful 
as it allows to dynamically determine collection name based on model objets 
class.
"""


class Collections(str, Enum):
    DATASET = "dataset"
    ACTIVITY = "activities"
    ACTIVITY_EXECUTION = "activity_executions"
    APPEARANCE = "appearances"
    ARRANGEMENT = "arrangements"
    CHANNEL = "channels"
    EXPERIMENT = "experiments"
    LIFE_ACTIVITY = "life_activities"
    MEASURE = "measures"
    MEASURE_NAME = "measure_names"
    MODALITY = "modalities"
    OBSERVABLE_INFORMATION = "observable_informations"
    PARTICIPANT = "participants"
    PARTICIPANT_STATE = "participant_states"
    PARTICIPATION = "participations"
    PERSONALITY = "personalities"
    RECORDING = "recordings"
    REGISTERED_CHANNEL = "registered_channels"
    REGISTERED_DATA = "registered_data"
    SCENARIO = "scenarios"
    TIME_SERIES = "timeSeries"


SUPERCLASSES_TO_COLLECTION_NAMES = {
    DatasetIn: Collections.DATASET,
    ActivityIn: Collections.ACTIVITY,
    ActivityExecutionPropertyIn: Collections.ACTIVITY_EXECUTION,
    ActivityExecutionRelationIn: Collections.ACTIVITY_EXECUTION,
    AppearanceOcclusionIn: Collections.APPEARANCE,
    AppearanceOcclusionOut: Collections.APPEARANCE,
    AppearanceSomatotypeIn: Collections.APPEARANCE,
    AppearanceSomatotypeOut: Collections.APPEARANCE,
    ArrangementIn: Collections.ARRANGEMENT,
    ChannelIn: Collections.CHANNEL,
    ExperimentIn: Collections.EXPERIMENT,
    LifeActivityIn: Collections.LIFE_ACTIVITY,
    MeasurePropertyIn: Collections.MEASURE,
    MeasureRelationIn: Collections.MEASURE,
    MeasureNameIn: Collections.MEASURE_NAME,
    ModalityIn: Collections.MODALITY,
    ObservableInformationIn: Collections.OBSERVABLE_INFORMATION,
    ParticipantIn: Collections.PARTICIPANT,
    ParticipantStatePropertyIn: Collections.PARTICIPANT_STATE,
    ParticipantStateRelationIn: Collections.PARTICIPANT_STATE,
    BasicParticipationOut: Collections.PARTICIPATION,
    ParticipationIn: Collections.PARTICIPATION,
    PersonalityBigFiveIn: Collections.PERSONALITY,
    PersonalityPanasIn: Collections.PERSONALITY,
    RecordingPropertyIn: Collections.RECORDING,
    RecordingRelationIn: Collections.RECORDING,
    BasicRegisteredChannelOut: Collections.REGISTERED_CHANNEL,
    RegisteredChannelIn: Collections.REGISTERED_CHANNEL,
    RegisteredDataIn: Collections.REGISTERED_DATA,
    ScenarioIn: Collections.SCENARIO,
    ScenarioOut: Collections.SCENARIO,
    TimeSeriesPropertyIn: Collections.TIME_SERIES,
    TimeSeriesRelationIn: Collections.TIME_SERIES,
}


def get_collection_name(model_class):
    """
    Get mongo collection name, based on the class of model object
    """
    for superclass, collection_name in SUPERCLASSES_TO_COLLECTION_NAMES.items():
        if issubclass(model_class, superclass):
            return collection_name
    raise ValueError(f"{model_class} class is not subclass of any model")
