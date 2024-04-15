from services.mongo_services import MongoServiceFactory


class MongoService:
    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(MongoService, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        self.service_factory = MongoServiceFactory()

    def get_service_factory(self):
        return self.service_factory


service = MongoService()