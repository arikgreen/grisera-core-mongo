from activity.activity_service_mongodb import ActivityServiceMongoDB
from activity_execution.activity_execution_service_mongodb import (
    ActivityExecutionServiceMongoDB,
)
from appearance.appearance_service_mongodb import AppearanceServiceMongoDB
from arrangement.arrangement_service_mongodb import ArrangementServiceMongoDB
from dataset.dataset_service_mongodb import DatasetServiceMongoDB
from experiment.experiment_service_mongodb import ExperimentServiceMongoDB
from observable_information.observable_information_service_mongodb import (
    ObservableInformationServiceMongoDB,
)
from personality.personality_service_mongodb import PersonalityServiceMongoDB
from scenario.scenario_service_mongodb import ScenarioServiceMongoDB
from grisera import ServiceFactory
from channel.channel_service_mongodb import ChannelServiceMongoDB
from life_activity.life_activity_service_mongodb import LifeActivityServiceMongoDB
from measure.measure_service_mongodb import MeasureServiceMongoDB
from measure_name.measure_name_service_mongodb import MeasureNameServiceMongoDB
from modality.modality_service_mongodb import ModalityServiceMongoDB
from participant.participant_service_mongodb import ParticipantServiceMongoDB
from participant_state.participant_state_service_mongodb import (
    ParticipantStateServiceMongoDB,
)
from participation.participation_service_mongodb import ParticipationServiceMongoDB
from recording.recording_service_mongodb import RecordingServiceMongoDB
from registered_channel.registered_channel_service_mongodb import (
    RegisteredChannelServiceMongoDB,
)
from registered_data.registered_data_service_mongodb import RegisteredDataServiceMongoDB
from time_series.time_series_service_mongodb import TimeSeriesServiceMongoDB
from grisera import ActivityService
from grisera import ActivityExecutionService
from grisera import AppearanceService
from grisera import ArrangementService
from grisera import ChannelService
from grisera import ExperimentService
from grisera import LifeActivityService
from grisera import MeasureService
from grisera import MeasureNameService
from grisera import ModalityService
from grisera import (
    ObservableInformationService,
)
from grisera import ParticipantService
from grisera import ParticipantStateService
from grisera import ParticipationService
from grisera import PersonalityService
from grisera import RecordingService
from grisera import RegisteredChannelService
from grisera import RegisteredDataService
from grisera import ScenarioService
from grisera import TimeSeriesService
from grisera import DatasetService


class MongoServiceFactory(ServiceFactory):
    def __init__(self):
        self.database_service = DatasetServiceMongoDB()
        self.channel_service = ChannelServiceMongoDB()
        self.recording_service = RecordingServiceMongoDB()
        self.registered_channel_service = RegisteredChannelServiceMongoDB()
        self.registered_data_service = RegisteredDataServiceMongoDB()
        self.observable_information_service = ObservableInformationServiceMongoDB()
        self.modality_service = ModalityServiceMongoDB()
        self.life_activity_service = LifeActivityServiceMongoDB()
        self.time_series_service = TimeSeriesServiceMongoDB()
        self.measure_service = MeasureServiceMongoDB()
        self.measure_name_service = MeasureNameServiceMongoDB()
        self.participation_service = ParticipationServiceMongoDB()
        self.participant_service = ParticipantServiceMongoDB()
        self.participant_state_service = ParticipantStateServiceMongoDB()
        self.appearance_service = AppearanceServiceMongoDB()
        self.personality_service = PersonalityServiceMongoDB()
        self.arrangement_service = ArrangementServiceMongoDB()
        self.activity_execution_service = ActivityExecutionServiceMongoDB()
        self.activity_service = ActivityServiceMongoDB()
        self.experiment_service = ExperimentServiceMongoDB()
        self.scenario_service = ScenarioServiceMongoDB()

        service_pairs = [
            ("registered_channel", "channel"),
            ("registered_channel", "registered_data"),
            ("registered_channel", "recording"),
            ("observable_information", "recording"),
            ("observable_information", "time_series"),
            ("observable_information", "life_activity"),
            ("observable_information", "modality"),
            ("measure", "time_series"),
            ("measure", "measure_name"),
            ("participation", "recording"),
            ("participant_state", "participation"),
            ("participant_state", "participant"),
            ("participant_state", "appearance"),
            ("participant_state", "personality"),
            ("activity_execution", "activity"),
            ("activity_execution", "arrangement"),
            ("activity_execution", "participation"),
            ("activity_execution", "scenario"),
            ("experiment", "scenario"),
        ]

        for first_service_name, second_service_name in service_pairs:
            self._pair_services(first_service_name, second_service_name)

    def get_dataset_service(self) -> DatasetService:
        return self.database_service

    def get_activity_service(self) -> ActivityService:
        return self.activity_service

    def get_activity_execution_service(self) -> ActivityExecutionService:
        return self.activity_execution_service

    def get_appearance_service(self) -> AppearanceService:
        return self.appearance_service

    def get_arrangement_service(self) -> ArrangementService:
        return self.arrangement_service

    def get_channel_service(self) -> ChannelService:
        return self.channel_service

    def get_experiment_service(self) -> ExperimentService:
        return self.experiment_service

    def get_life_activity_service(self) -> LifeActivityService:
        return self.life_activity_service

    def get_measure_service(self) -> MeasureService:
        return self.measure_service

    def get_measure_name_service(self) -> MeasureNameService:
        return self.measure_name_service

    def get_modality_service(self) -> ModalityService:
        return self.modality_service

    def get_observable_information_service(self) -> ObservableInformationService:
        return self.observable_information_service

    def get_participant_service(self) -> ParticipantService:
        return self.participant_service

    def get_participant_state_service(self) -> ParticipantStateService:
       return self.participant_state_service

    def get_participation_service(self) -> ParticipationService:
        return self.participation_service

    def get_personality_service(self) -> PersonalityService:
        return self.personality_service

    def get_recording_service(self) -> RecordingService:
        return self.recording_service

    def get_registered_channel_service(self) -> RegisteredChannelService:
        return self.registered_channel_service

    def get_registered_data_service(self) -> RegisteredDataService:
        return self.registered_data_service

    def get_scenario_service(self) -> ScenarioService:
        return self.scenario_service

    def get_time_series_service(self) -> TimeSeriesService:
        return self.time_series_service

    def _pair_services(
        self, first_service_collection_name: str, second_service_collection_name: str
    ):
        """
        Take collection names and their references to each other. For example:
        self._paid_services('channel', 'registered_channel')
        is equivalent to:
        self.channel_service.registered_channel_service = (
            self.registered_channel_service
        )
        self.registered_channel_service.channel_service = (
            self.channel_service
        )
        """
        first_service_attr = f"{first_service_collection_name}_service"
        second_service_attr = f"{second_service_collection_name}_service"

        first_service = getattr(self, first_service_attr)
        second_service = getattr(self, second_service_attr)

        setattr(first_service, second_service_attr, second_service)
        setattr(second_service, first_service_attr, first_service)
