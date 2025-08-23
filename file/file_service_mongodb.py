from datetime import datetime
from typing import Union, List, Optional

from grisera.file.file_service import FileService
from grisera.file.file_model import BasicFileOut, FilesOut, FileIn

from mongo_service import MongoApiService
from mongo_service.service_mixins import GenericMongoServiceMixin
from mongo_service.mongodb_api_config import mongo_database_name


class FileServiceMongoDB(FileService, GenericMongoServiceMixin):
    """
    Object to handle logic of files requests with MongoDB persistence

    Attributes:
        mongo_api_service (MongoApiService): MongoDB service for database operations
        model_out_class: Output model class for HATEOAS
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.model_out_class = BasicFileOut

    def save_file_metadata(self, filename: str, original_filename: str, name: str, size: int, 
                          content_type: str, dataset_id: Union[int, str]) -> BasicFileOut:
        """
        Save file metadata to MongoDB

        Args:
            filename (str): Generated filename in storage
            original_filename (str): Original filename
            name (str): Custom name given by user
            size (int): File size
            content_type (str): MIME type
            dataset_id (Union[int, str]): Associated dataset ID

        Returns:
            BasicFileOut: Created file metadata
        """
        file_data = FileIn(
            filename=filename,
            original_filename=original_filename,
            name=name,
            size=size,
            content_type=content_type,
            dataset_id=str(dataset_id) if dataset_id else None
        )
        
        result = self.create(file_data, mongo_database_name)
        return result

    def get_files(self) -> list:
        """
        Get all files from MongoDB

        Returns:
            list: List of all files
        """
        results_dict = self.get_multiple(mongo_database_name, query={})
        results = [BasicFileOut(**result) for result in results_dict]
        return results

    def get_file_by_id(self, file_id: Union[int, str]) -> Optional[BasicFileOut]:
        """
        Get file by ID from MongoDB

        Args:
            file_id (Union[int, str]): File ID

        Returns:
            Optional[BasicFileOut]: File metadata if found
        """
        try:
            result = self.get_single(file_id, mongo_database_name)
            return result
        except:
            return None

    def delete_file(self, file_id: Union[int, str]) -> bool:
        """
        Delete file metadata from MongoDB

        Args:
            file_id (Union[int, str]): File ID

        Returns:
            bool: True if deleted, False if not found
        """
        try:
            self.delete(file_id, mongo_database_name)
            return True
        except:
            return False

    def get_files_by_dataset(self, dataset_id: Union[int, str]) -> list:
        """
        Get files by dataset ID

        Args:
            dataset_id (Union[int, str]): Dataset ID

        Returns:
            list: List of files for the dataset
        """
        results_dict = self.get_multiple(mongo_database_name, query={
            "dataset_id": str(dataset_id)
        })
        results = [BasicFileOut(**result) for result in results_dict]
        return results

    def _add_related_documents(self, file_dict: dict, dataset_id: Union[int, str], depth: int, source: str):
        """
        Add related documents to file. Files don't have complex relations, so this is empty.
        
        Args:
            file_dict (dict): File dictionary to enhance with related documents
            dataset_id (Union[int, str]): Dataset ID
            depth (int): Depth of relations to fetch
            source (str): Source collection name
        """
        pass