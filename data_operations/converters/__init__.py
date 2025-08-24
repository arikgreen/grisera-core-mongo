"""
Refactored entity converters - separated into individual modules for better maintainability.
"""

from .base import BaseEntityConverter
from .activity_converter import ActivityConverter
from .channel_converter import ChannelConverter
from .arrangement_converter import ArrangementConverter
from .modality_converter import ModalityConverter
from .life_activity_converter import LifeActivityConverter
from .measure_name_converter import MeasureNameConverter
from .measure_converter import MeasureConverter
from .participant_converter import ParticipantConverter
from .participant_state_converter import ParticipantStateConverter
from .time_series_converter import TimeSeriesConverter
from .experiment_converter import ExperimentConverter
from .activity_execution_converter import ActivityExecutionConverter
from .participation_converter import ParticipationConverter
from .registered_data_converter import RegisteredDataConverter
from .registered_channel_converter import RegisteredChannelConverter
from .recording_converter import RecordingConverter
from .observable_information_converter import ObservableInformationConverter
from .appearance_converter import AppearanceConverter

# Registry of all entity converters
ENTITY_CONVERTERS = {
    "Activity": ActivityConverter,
    "Channel": ChannelConverter,
    "MeasureName": MeasureNameConverter,
    "Measure": MeasureConverter,
    "Modality": ModalityConverter,
    "LifeActivity": LifeActivityConverter,
    "Arrangement": ArrangementConverter,
    "Participant": ParticipantConverter,
    "ParticipantState": ParticipantStateConverter,
    "TimeSeries": TimeSeriesConverter,
    "Experiment": ExperimentConverter,
    "ActivityExecution": ActivityExecutionConverter,
    "Participation": ParticipationConverter,
    "Recording": RecordingConverter,
    "RegisteredData": RegisteredDataConverter,
    "RegisteredChannel": RegisteredChannelConverter,
    "ObservableInformation": ObservableInformationConverter,
    "Appearance": AppearanceConverter,
}

__all__ = [
    "ENTITY_CONVERTERS",
    "BaseEntityConverter",
    "ActivityConverter",
    "ChannelConverter", 
    "ArrangementConverter",
    "ModalityConverter",
    "LifeActivityConverter",
    "MeasureNameConverter",
    "MeasureConverter",
    "ParticipantConverter",
    "ParticipantStateConverter",
    "TimeSeriesConverter",
    "ExperimentConverter",
    "ActivityExecutionConverter",
    "ParticipationConverter",
    "RegisteredDataConverter",
    "RegisteredChannelConverter",
    "RecordingConverter",
    "ObservableInformationConverter",
    "AppearanceConverter",
]


