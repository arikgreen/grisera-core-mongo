import mongomock

from grisera import RegisteredChannelIn
from grisera import NotFoundByIdModel
from grisera import RegisteredDataIn
from mongo_service.mongodb_api_config import mongo_api_host, mongo_api_port
from services.mongo_service import service as mongo_service
from unittest import TestCase

class TestMongoRegisteredData(TestCase):
    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_save(self):
        service = mongo_service.get_service_factory().get_registered_data_service()
        rd = RegisteredDataIn(source="source")
        created_rd = service.save_registered_data(rd)
        self.assertEqual(created_rd.source, rd.source)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_get(self):
        service = mongo_service.get_service_factory().get_registered_data_service()
        rd = RegisteredDataIn(source="source")
        created_rd = service.save_registered_data(rd)
        fetched_rd = service.get_registered_data(created_rd.id)
        self.assertEqual(created_rd.source, fetched_rd.source)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_update(self):
        service = mongo_service.get_service_factory().get_registered_data_service()
        rd = RegisteredDataIn(source="source")
        created_rd = service.save_registered_data(rd)

        new_source = "changed_source"
        created_rd.source = new_source
        service.update_registered_data(created_rd.id, created_rd)
        fetched_rd = service.get_registered_data(created_rd.id)
        self.assertEqual(fetched_rd.source, new_source)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_delete(self):
        service = mongo_service.get_service_factory().get_registered_data_service()
        rd = RegisteredDataIn(source="source")
        created_rd = service.save_registered_data(rd)
        service.delete_registered_data(created_rd.id)
        get_result = service.get_registered_data(created_rd.id)
        self.assertTrue(type(get_result) is NotFoundByIdModel)

    @mongomock.patch(servers=((mongo_api_host, mongo_api_port),))
    def test_traverse_one(self):
        registered_data_service = mongo_service.get_service_factory().get_registered_data_service()
        registered_channel_service = mongo_service.get_service_factory().get_registered_channel_service()

        rd = RegisteredDataIn(source="source")
        created_rd = registered_data_service.save_registered_data(rd)
        registered_channels_count = 10
        created_registered_channels = []
        for _ in range(registered_channels_count):
            registered_channel = RegisteredChannelIn(registered_data_id=created_rd.id)
            created_rc = registered_channel_service.save_registered_channel(
                registered_channel
            )
            created_registered_channels.append(created_rc)

        # create registered channels related to other channel
        other_rd = registered_data_service.save_registered_data(
            RegisteredDataIn(source="other_source")
        )
        for _ in range(5):
            unrelated_registered_channel = RegisteredChannelIn(
                registered_data_id=other_rd.id
            )
            registered_channel_service.save_registered_channel(
                unrelated_registered_channel
            )

        result = registered_data_service.get_registered_data(created_rd.id, depth=1)
        self.assertFalse(type(result) is NotFoundByIdModel)
        self.assertEqual(len(result.registered_channels), registered_channels_count)
        expected_created_ids = {rc.id for rc in created_registered_channels}
        created_ids = {rc.id for rc in result.registered_channels}
        self.assertSetEqual(expected_created_ids, created_ids)
        # check whether too much models weren't fetched
        self.assertIsNone(result.registered_channels[0].channel)
        self.assertIsNone(result.registered_channels[0].registeredData)
