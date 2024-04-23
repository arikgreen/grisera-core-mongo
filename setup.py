from grisera import ActivityIn, Activity
from grisera import ActivityService
from grisera import ArrangementIn, Arrangement
from grisera import ArrangementService
from grisera import ChannelIn, ChannelType
from grisera import ChannelService
from grisera import LifeActivityIn, LifeActivity
from grisera import LifeActivityService
from grisera import MeasureNameIn, MeasureName
from grisera import MeasureNameService
from grisera import ModalityIn, Modality
from grisera import ModalityService


class SetupNodes:
    """
    Class to init nodes in graph database
    """

    def set_activities(self):
        """
        Initialize values of activities
        """
        activity_service = ActivityService()
        created_activities = [activity.activity for activity in activity_service.get_activities().activities]
        [activity_service.save_activity(ActivityIn(activity=activity_activity.value))
         for activity_activity in Activity
         if activity_activity.value not in created_activities]

    def set_channels(self):
        """
        Initialize values of channels
        """
        channel_service = ChannelService()
        created_types = [channel.type for channel in channel_service.get_channels().channels]
        [channel_service.save_channel(ChannelIn(type=channel_type.value))
         for channel_type in ChannelType
         if channel_type.value not in created_types]


    def set_arrangements(self):
        """
        Initialize values of arrangement distances
        """
        arrangement_service = ArrangementService()
        created_arrangements = \
            [arrangement.arrangement_distance
             for arrangement in
             arrangement_service.get_arrangements().arrangements]
        [arrangement_service.save_arrangement(
            ArrangementIn(arrangement_type=arrangement.value[0], arrangement_distance=arrangement.value[1]))
            for arrangement in Arrangement
            if arrangement.value[1] not in created_arrangements]


    def set_modalities(self):
        """
        Initialize values of modalities
        """
        modality_service = ModalityService()
        created_modalities = [modality.modality for modality in modality_service.get_modalities().modalities]
        [modality_service.save_modality(ModalityIn(modality=modality_modality.value))
         for modality_modality in Modality
         if modality_modality.value not in created_modalities]


    def set_life_activities(self):
        """
        Initialize values of life activities
        """
        life_activity_service = LifeActivityService()
        created_types = [life_activity.life_activity for life_activity in
                         life_activity_service.get_life_activities().life_activities]

        [life_activity_service.save_life_activity(LifeActivityIn(life_activity=life_activity_life_activity.value))
         for life_activity_life_activity in LifeActivity
         if life_activity_life_activity.value not in created_types]


    def set_measure_names(self):
        """
        Initialize values of measure names
        """
        measure_name_service = MeasureNameService()
        created_names = [measure_name.name for measure_name in
                         measure_name_service.get_measure_names().measure_names]
        [measure_name_service.save_measure_name(
            MeasureNameIn(name=measure_name.value[0], type=measure_name.value[1]))
            for measure_name in MeasureName
            if measure_name.value[0] not in created_names]
