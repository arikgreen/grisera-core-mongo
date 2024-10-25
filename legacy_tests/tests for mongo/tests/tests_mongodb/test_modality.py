import mongomock

from grisera import RecordingIn
from grisera import ObservableInformationIn
from grisera import NotFoundByIdModel
from grisera import ModalityIn
from mongo_service.mongodb_api_config import mongo_api_host, mongo_api_port
from services.mongo_service import service
from unittest import TestCase

class TestMongoModality(TestCase):
    def generate_observable_information(self, modality_id):
        recording_service = service.get_service_factory().get_recording_service()
        recording = recording_service.save_recording(RecordingIn())
        oi = ObservableInformationIn(recording_id=recording.id, modality_id=modality_id)
        observable_information_service = service.get_service_factory().get_observable_information_service()
        return observable_information_service.save_observable_information(oi)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_save(self):
        modality_service = service.get_service_factory().get_modality_service()
        modality = ModalityIn(modality="Test modality")
        created_modality = modality_service.save_modality(modality)
        self.assertEqual(created_modality.modality, modality.modality)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_get(self):
        modality_service = service.get_service_factory().get_modality_service()
        modality = ModalityIn(modality="Test modality")
        created_modality = modality_service.save_modality(modality)
        fetched_modality = modality_service.get_modality(created_modality.id)
        self.assertEqual(fetched_modality.modality, created_modality.modality)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_get_all(self):
        modality_service = service.get_service_factory().get_modality_service()
        created_modalities_count = 10
        created_modalities = []
        for i in range(created_modalities_count):
            modality = ModalityIn(modality=f"Test modality {i}")
            created_modalities.append(modality_service.save_modality(modality))
        result = modality_service.get_modalities()
        self.assertEqual(len(result.modalities), created_modalities_count)
        created_modalities_ids = set(modality.id for modality in created_modalities)
        fetched_modalities_ids = set(modality.id for modality in result.modalities)
        self.assertSetEqual(created_modalities_ids, fetched_modalities_ids)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_traverse_one(self):
        modality_service = service.get_service_factory().get_modality_service()

        modality = ModalityIn(modality="Test modality")
        created_modality = modality_service.save_modality(modality)
        created_oi_count = 10
        created_oi = []
        for _ in range(created_oi_count):
            created_oi.append(
                self.generate_observable_information(modality_id=created_modality.id)
            )

        # create modalities related to other observable information
        other_modality = modality_service.save_modality(
            ModalityIn(modality="Other test modality")
        )
        for _ in range(5):
            self.generate_observable_information(modality_id=other_modality.id)

        result = modality_service.get_modality(created_modality.id, depth=1)
        self.assertFalse(type(result) is NotFoundByIdModel)
        self.assertEqual(len(result.observable_informations), created_oi_count)
        expected_created_ids = set(oi.id for oi in created_oi)
        created_ids = set(oi.id for oi in result.observable_informations)
        self.assertSetEqual(expected_created_ids, created_ids)
        # check whether too much models weren't fetched
        self.assertIsNone(result.observable_informations[0].recording)
