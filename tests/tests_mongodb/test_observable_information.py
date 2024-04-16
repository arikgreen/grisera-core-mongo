import mongomock

from grisera import LifeActivityIn
from grisera import ModalityIn
from grisera import ObservableInformationIn
from grisera import NotFoundByIdModel
from mongo_service.mongodb_api_config import mongo_api_host, mongo_api_port
from grisera import RecordingIn
from services.mongo_service import service
from unittest import TestCase

class TestMongoOservableInformation(TestCase):
    def generate_recording(self, save: bool):
        recording = RecordingIn()
        if not save:
            return recording
        return service.get_service_factory().get_recording_service().save_recording(recording)

    def generate_modality(self, save: bool):
        modality = ModalityIn(modality="A modality")
        if not save:
            return modality
        return service.get_service_factory().get_modality_service().save_modality(modality)

    def generate_life_activity(self, save: bool):
        life_activity = LifeActivityIn(life_activity="movement")
        if not save:
            return life_activity
        return service.get_service_factory().get_life_activity_service().save_life_activity(life_activity)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_create(self):
        observable_information_service = service.get_service_factory().get_observable_information_service()
        recording = self.generate_recording(save=True)
        observable_information = ObservableInformationIn(recording_id=recording.id)
        created_oi = observable_information_service.save_observable_information(observable_information)
        self.assertEqual(created_oi.recording_id, recording.id)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_get(self):
        observable_information_service = service.get_service_factory().get_observable_information_service()
        recording = self.generate_recording(save=True)
        observable_information = ObservableInformationIn(recording_id=recording.id)
        created_oi = observable_information_service.save_observable_information(observable_information)
        fetched_oi = observable_information_service.get_observable_information(created_oi.id)
        self.assertFalse(type(fetched_oi) is NotFoundByIdModel)
        self.assertEqual(fetched_oi.recording_id, recording.id)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_delete(self):
        observable_information_service = service.get_service_factory().get_observable_information_service()

        recording = self.generate_recording(save=True)
        observable_information = ObservableInformationIn(recording_id=recording.id)
        created_oi = observable_information_service.save_observable_information(observable_information)
        other_oi = observable_information_service.save_observable_information(
            ObservableInformationIn(recording_id=recording.id)
        )
        observable_information_service.delete_observable_information(created_oi.id)

        get_result = observable_information_service.get_observable_information(created_oi.id)
        self.assertTrue(type(get_result) is NotFoundByIdModel)
        # check wether other oi related to this recording wasn't deleted
        get_other_result = observable_information_service.get_observable_information(other_oi.id)
        self.assertFalse(type(get_other_result) is NotFoundByIdModel)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_traverse_one(self):
        observable_information_service = service.get_service_factory().get_observable_information_service()

        recording = self.generate_recording(save=True)
        modality = self.generate_modality(save=True)
        life_activity = self.generate_life_activity(save=True)
        observable_information = ObservableInformationIn(
            recording_id=recording.id,
            modality_id=modality.id,
            life_activity_id=life_activity.id,
        )
        created_oi = observable_information_service.save_observable_information(observable_information)

        fetched_oi = observable_information_service.get_observable_information(created_oi.id, depth=1)
        self.assertFalse(type(fetched_oi) is NotFoundByIdModel)
        self.assertEqual(fetched_oi.recording.id, recording.id)
        self.assertEqual(fetched_oi.modality.id, modality.id)
        self.assertEqual(fetched_oi.modality.modality, modality.modality)
        self.assertEqual(fetched_oi.life_activity.id, life_activity.id)
        self.assertEqual(
            fetched_oi.life_activity.life_activity, life_activity.life_activity
        )
