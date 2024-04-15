from abc import ABC, abstractmethod
from typing import Union

from pydantic import BaseModel
from mongo_service.collection_mapping import get_collection_name
from grisera import NotFoundByIdModel
from mongo_service import MongoApiService


class GenericMongoServiceMixin:

    """
    This mixin defines implementation of basic mongo services methods. It requires the subclass to implement:
        model_out_class field - out model class of services model. Based on this attribute mongo collection is
            determined
        _add_related_documents method - method for adding related documents to result when traversing models
    """

    def __init__(self):
        self.mongo_api_service = MongoApiService()

    def create(self, object_in: BaseModel):
        """
        Generic method for sending request to mongo api to create new document

        Args:
            object_in: Object based on which document is to be created

        Returns:
            Result of request as data object
        """
        created_document_id = self.mongo_api_service.create_document(object_in)

        return self.get_single(created_document_id)

    def get_multiple(
        self, query: dict = {}, depth: int = 0, source: str = "", *args, **kwargs
    ):
        """
        Generic method for getting a multiple documents from mongo api

        Args:
            query: Query to mongo api. Empty by default.
            depth: This specifies the number of collections that are to be traversed
            source: Helper arguments that specifies direction of collection traversion

        Returns:
            Result of request as list of dictionaries
        """
        collection_name = get_collection_name(self.model_out_class)
        results_dict = self.mongo_api_service.get_documents(
            collection_name, query, *args, **kwargs
        )

        for result in results_dict:
            self._add_related_documents(result, depth, source)

        return results_dict

    def get_single_dict(
        self, id: Union[str, int], depth: int = 0, source: str = "", *args, **kwargs
    ):
        """
        Generic method for getting a single document in dict form from mongo api.

        Args:
            id: Id of the document.
            depth: This specifies the number of collections that are to be traversed
            source: Helper arguments that specifies direction of collection traversion

        Returns:
            Result of request as a dictionary
        """
        collection_name = get_collection_name(self.model_out_class)
        result_dict = self.mongo_api_service.get_document(
            id, collection_name, *args, **kwargs
        )

        if type(result_dict) is NotFoundByIdModel:
            return result_dict

        self._add_related_documents(result_dict, depth, source)

        return result_dict

    def get_single(
        self, id: Union[str, int], depth: int = 0, source: str = "", *args, **kwargs
    ):
        """
        Generic method for getting a single document from mongo api.

        Args:
            id: Id of the document.
            depth: This specifies the number of collections that are to be traversed
            source: Helper arguments that specifies direction of collection traversion

        Returns:
            Result of request as a model object
        """
        out_class = self.model_out_class
        result = self.get_single_dict(id, depth, source, *args, **kwargs)
        if type(result) is NotFoundByIdModel:
            return result
        return out_class(**result)

    def update(self, id: Union[str, int], updated_object: BaseModel):
        """
        Generic method for sending request to mongo api to update single document

        Args:
            id: Id of document to be updated.
            updated_object: New version of document as model object

        Returns:
            Updated object
        """
        get_response = self.get_single(id)

        if type(get_response) is NotFoundByIdModel:
            return get_response

        self.mongo_api_service.update_document(id, updated_object)

        return self.get_single(id)

    def delete(self, id: Union[str, int]):
        """
        Generic method for delete request to mongo api

        Args:
            id: Id of document to be deleted.

        Returns:
            Deleted object
        """
        existing_document = self.get_single(id)

        if existing_document is None:
            return NotFoundByIdModel(
                id=id,
                errors={"errors": "document with such id not found"},
            )

        self.mongo_api_service.delete_document(existing_document)
        return existing_document
