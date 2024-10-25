from unittest import TestCase

import mongomock

from grisera import LifeActivityIn
from grisera import RecordingIn
from grisera import ObservableInformationIn
from grisera import NotFoundByIdModel
from mongo_service.mongodb_api_config import mongo_api_host, mongo_api_port
from services.mongo_service import service
from unittest import TestCase

class TestMongoLifeActivity(TestCase):
    def generate_observable_information(self, life_activity_id):
        recording_service = service.get_service_factory().get_recording_service()
        recording = recording_service.save_recording(RecordingIn())
        oi = ObservableInformationIn(
            recording_id=recording.id, life_activity_id=life_activity_id
        )
        observable_information_service = service.get_service_factory().get_observable_information_service()
        return observable_information_service.save_observable_information(oi)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_save(self):
        life_activity_service = service.get_service_factory().get_life_activity_service()
        life_activity = LifeActivityIn(life_activity="movement")
        created_life_activity = life_activity_service.save_life_activity(life_activity)
        self.assertEqual(
            created_life_activity.life_activity, life_activity.life_activity
        )

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_get(self):
        life_activity_service = service.get_service_factory().get_life_activity_service()
        life_activity = LifeActivityIn(life_activity="movement")
        created_life_activity = life_activity_service.save_life_activity(life_activity)
        fetched_life_activity = life_activity_service.get_life_activity(created_life_activity.id)
        self.assertEqual(
            fetched_life_activity.life_activity, created_life_activity.life_activity
        )

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_get_all(self):
        life_activity_service = service.get_service_factory().get_life_activity_service()
        created_la_count = 10
        created_la = []
        for i in range(created_la_count):
            life_activity = LifeActivityIn(life_activity="movement")
            created_la.append(life_activity_service.save_life_activity(life_activity))
        result = life_activity_service.get_life_activities()
        self.assertEqual(len(result.life_activities), created_la_count)
        created_la_ids = set(la.id for la in created_la)
        fetched_la_ids = set(la.id for la in result.life_activities)
        self.assertSetEqual(created_la_ids, fetched_la_ids)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_traverse_one(self):
        life_activity_service = service.get_service_factory().get_life_activity_service()

        life_activity = LifeActivityIn(life_activity="movement")
        created_life_activity = life_activity_service.save_life_activity(life_activity)
        created_oi_count = 10
        created_oi = []
        for _ in range(created_oi_count):
            created_oi.append(
                self.generate_observable_information(
                    life_activity_id=created_life_activity.id
                )
            )

        # create life activities related to other observable information
        other_life_activity = life_activity_service.save_life_activity(
            LifeActivityIn(life_activity="sound")
        )
        for _ in range(5):
            self.generate_observable_information(
                life_activity_id=other_life_activity.id
            )

        result = life_activity_service.get_life_activity(created_life_activity.id, depth=1)
        self.assertFalse(type(result) is NotFoundByIdModel)
        self.assertEqual(len(result.observable_informations), created_oi_count)
        expected_created_ids = set(oi.id for oi in created_oi)
        created_ids = set(oi.id for oi in result.observable_informations)
        self.assertSetEqual(expected_created_ids, created_ids)
        # check whether too much models weren't fetched
        self.assertIsNone(result.observable_informations[0].recording)
