from typing import Union

from mongo_service import MongoApiService
from mongo_service.service_mixins import GenericMongoServiceMixin
from grisera import (
    AdditionalParameterIn,
    AdditionalParametersOut,
    BasicAdditionalParameterOut,
    AdditionalParameterOut,
    NotFoundByIdModel,
    AdditionalParameterService,
)


class AdditionalParameterServiceMongoDB(AdditionalParameterService, GenericMongoServiceMixin):
    """
    Object to handle logic of additional parameters requests for MongoDB backend.

    Attributes:
    mongo_api_service (MongoApiService): Service used to communicate with Mongo API
    model_out_class (Type[BaseModel]): Out class of the model, used by GenericMongoServiceMixin
    """

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()
        self.model_out_class = AdditionalParameterOut

    def save_additional_parameter(self, parameter: AdditionalParameterIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to create new additional parameter

        Args:
            parameter (AdditionalParameterIn): Additional parameter to be added
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as additional parameter object
        """
        try:
            # Generate key if not provided
            if not parameter.key:
                parameter.key = parameter.name.lower().replace(" ", "_")

            return self.create(parameter, dataset_id)
                
        except Exception as e:
            # Return with minimum required fields when there's an error
            return AdditionalParameterOut(
                errors=str(e),
                name=parameter.name if hasattr(parameter, 'name') else "",
                type=parameter.type if hasattr(parameter, 'type') else "participant"
            )

    def get_additional_parameters(self, dataset_id: Union[int, str]):
        """
        Send request to mongo api to get additional parameters

        Args:
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as list of additional parameters objects
        """
        try:
            results_dict = self.get_multiple(dataset_id, {})
            parameters = [BasicAdditionalParameterOut(**result) for result in results_dict]
            return AdditionalParametersOut(parameters=parameters)
            
        except Exception as e:
            return AdditionalParametersOut(errors=str(e))

    def get_additional_parameter(self, parameter_id: Union[int, str], dataset_id: Union[int, str]):
        """
        Send request to mongo api to get given additional parameter

        Args:
            parameter_id (int | str): identity of additional parameter
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as additional parameter object
        """
        try:
            return self.get_single(parameter_id, dataset_id)
                
        except Exception as e:
            return NotFoundByIdModel(errors=str(e))

    def delete_additional_parameter(self, parameter_id: Union[int, str], dataset_id: Union[int, str]):
        """
        Send request to mongo api to delete given additional parameter

        Args:
            parameter_id (int | str): identity of additional parameter
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as additional parameter object
        """
        try:
            return self.delete(parameter_id, dataset_id)
                
        except Exception as e:
            return NotFoundByIdModel(errors=str(e))

    def update_additional_parameter(self, parameter_id: Union[int, str], parameter: AdditionalParameterIn, dataset_id: Union[int, str]):
        """
        Send request to mongo api to update given additional parameter

        Args:
            parameter_id (int | str): identity of additional parameter
            parameter (AdditionalParameterIn): Properties to update
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as additional parameter object
        """
        try:
            # Generate key if not provided
            if not parameter.key:
                parameter.key = parameter.name.lower().replace(" ", "_")

            return self.update(parameter_id, parameter, dataset_id)
                
        except Exception as e:
            return NotFoundByIdModel(errors=str(e))

    def get_additional_parameters_by_dataset(self, dataset_id: Union[int, str]):
        """
        Send request to mongo api to get additional parameters for given dataset

        Args:
            dataset_id (int | str): name of dataset

        Returns:
            Result of request as list of additional parameters objects
        """
        return self.get_additional_parameters(dataset_id)

    def _add_related_documents(self, parameter: dict, dataset_id: Union[int, str], depth: int, source: str):
        """
        Add related documents to parameter. AdditionalParameter has no related documents,
        so this method does nothing.
        
        Args:
            parameter (dict): Parameter document to add relations to
            dataset_id (int | str): name of dataset
            depth (int): traversal depth
            source (str): source collection name
        """
        # AdditionalParameter has no related documents
        pass