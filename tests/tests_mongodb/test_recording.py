import mongomock

from grisera import ObservableInformationIn
from grisera import RegisteredChannelIn
from grisera import NotFoundByIdModel
from mongo_service.mongodb_api_config import mongo_api_host, mongo_api_port
from grisera import RecordingIn
from services.mongo_service import service as mongo_service
from unittest import TestCase

class TestMongoRegisteredData(TestCase):
    def generate_registered_channel(self, save: bool):
        registered_channel = RegisteredChannelIn()
        if not save:
            return registered_channel
        service = mongo_service.get_service_factory().get_registered_channel_service()
        return service.save_registered_channel(registered_channel)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_get(self):
        service = mongo_service.get_service_factory().get_recording_service()
        recording = RecordingIn()
        created_recording = service.save_recording(recording)
        fetched_recording = service.get_recording(created_recording.id)
        self.assertFalse(type(fetched_recording) is NotFoundByIdModel)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_update_relationships(self):
        service = mongo_service.get_service_factory().get_recording_service()

        related_rc = self.generate_registered_channel(save=True)
        recording = RecordingIn(registered_channel_id=related_rc.id)
        created_recording = service.save_recording(recording)

        new_related_rc = self.generate_registered_channel(save=True)
        created_recording.registered_channel_id = new_related_rc.id
        service.update_recording_relationships(created_recording.id, created_recording)
        fetched_recording = service.get_recording(created_recording.id)
        self.assertEqual(fetched_recording.registered_channel_id, new_related_rc.id)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_delete(self):
        service = mongo_service.get_service_factory().get_recording_service()
        recording = RecordingIn()
        created_recording = service.save_recording(recording)
        service.delete_recording(created_recording.id)
        get_result = service.get_recording(created_recording.id)
        self.assertTrue(type(get_result) is NotFoundByIdModel)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_traverse_one(self):
        service = mongo_service.get_service_factory().get_recording_service()
        observable_information_service = mongo_service.get_service_factory().get_observable_information_service()

        related_rc = self.generate_registered_channel(save=True)
        recording = RecordingIn(registered_channel_id=related_rc.id)
        created_recording = service.save_recording(recording)

        obserbable_informations_count = 10
        created_obserbable_informations = []
        for _ in range(obserbable_informations_count):
            oi = ObservableInformationIn(recording_id=created_recording.id)
            created_oi = observable_information_service.save_observable_information(oi)
            created_obserbable_informations.append(created_oi)

        # create observable informations related to other recording
        other_recording = service.save_recording(
            RecordingIn(registered_channel_id=related_rc.id)
        )
        for _ in range(5):
            unrelated_oi = ObservableInformationIn(recording_id=other_recording.id)
            observable_information_service.save_observable_information(unrelated_oi)

        result = service.get_recording(created_recording.id, depth=1)
        self.assertFalse(type(result) is NotFoundByIdModel)
        self.assertEqual(
            len(result.observable_informations), obserbable_informations_count
        )
        expected_created_ids = {oi.id for oi in created_obserbable_informations}
        created_ids = {oi.id for oi in result.observable_informations}
        self.assertSetEqual(expected_created_ids, created_ids)
