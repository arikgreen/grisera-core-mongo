from typing import Union, List

from grisera import DatasetService, BasicDatasetOut, DatasetsOut
from grisera import DatasetOut, DatasetIn


from mongo_service import MongoApiService
from mongo_service.service_mixins import GenericMongoServiceMixin
from mongo_service.mongodb_api_config import mongo_database_name


class DatasetServiceMongoDB(DatasetService, GenericMongoServiceMixin):
    """
    Object to handle logic of datasets requests
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.model_out_class = DatasetOut

    def save_dataset(self, dataset: DatasetIn):
        return self.create(dataset, mongo_database_name)

    def get_datasets(self, dataset_ids: List[Union[int, str]]):
        results_dict = self.get_multiple(mongo_database_name, query={
            "_id": self.mongo_api_service.get_id_in_query(dataset_ids)
        })
        results = [BasicDatasetOut(**result) for result in results_dict]
        return DatasetsOut(datasets=results)

    def get_dataset(self, dataset_id: Union[int, str]):
        return self.get_single(dataset_id, mongo_database_name)

    def delete_dataset(self, dataset_id: Union[int, str]):
        return self.delete(dataset_id, mongo_database_name)

    def update_dataset(self, dataset_id: Union[int, str], dataset: DatasetIn):
        return self.update(dataset_id, dataset, mongo_database_name)

    def _add_related_documents(self, participant: dict, dataset_id: Union[int, str], depth: int, source: str):
        pass