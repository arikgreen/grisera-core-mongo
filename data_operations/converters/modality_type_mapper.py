from typing import Optional, Callable
import re

from mongo_service.collection_mapping import Collections


class ModalityTypeMapper:
    """
    Mapuje stringi typu modalności (np. 'co:modalityFacialExpressions')
    na MongoDB ID, z automatyczną aktualizacją external_id gdy pusty.
    """

    def __init__(self, mongo_api_service, logger):
        self.mongo_api_service = mongo_api_service
        self.logger = logger

    def _camel_case_to_snake_case(self, camel_case: str) -> str:
        """
        Konwertuj CamelCase na snake_case.
        FacialExpressions -> facial_expressions
        """
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_case)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def map_to_mongodb_id(
        self,
        modality_type_string: str,
        dataset_id: str,
        import_id: str = None,
        log_import_error_func: Optional[Callable] = None
    ) -> Optional[str]:
        """
        Mapuje string typu modalności na MongoDB ID.
        co:modalityFacialExpressions -> szukaj "facial expressions" -> zwróć MongoDB ID
        Aktualizuje external_id jeśli pusty.

        Args:
            modality_type_string (str): String z JSON-a (np. 'co:modalityFacialExpressions')
            dataset_id (str): ID datasetu
            import_id (str): ID importu (opcjonalne, do logowania)
            log_import_error_func (Callable): Funkcja do logowania błędów importu

        Returns:
            Optional[str]: MongoDB ID modality lub None
        """
        from grisera.modality.modality_model import Modality

        try:
            # 1. Wyciągnij część po ':' i usuń 'modality'
            type_part = modality_type_string.split(':')[-1]
            if type_part.lower().startswith('modality'):
                normalized = type_part[8:]
            else:
                normalized = type_part

            # 2. CamelCase -> snake_case
            snake_case_name = self._camel_case_to_snake_case(normalized)

            # 3. Szukaj w enum Modality
            matching_modality = None
            for modality in Modality:
                if modality.name == snake_case_name:
                    matching_modality = modality
                    break

            if not matching_modality:
                error_msg = f"Could not match modality type '{modality_type_string}' to any known Modality enum value"
                self.logger.log_error(error_msg)
                if log_import_error_func:
                    log_import_error_func(
                        import_id,
                        dataset_id,
                        "MODALITY_TYPE_NOT_FOUND",
                        error_msg,
                        modality_type_string
                    )
                return None

            # 4. Szukaj w MongoDB
            modality_value = matching_modality.value
            query = {"modality": modality_value}
            modalities = self.mongo_api_service.get_documents(
                collection_name=Collections.MODALITY.value,
                dataset_id=dataset_id,
                query=query
            )

            if not modalities:
                error_msg = f"Modality '{modality_value}' not found in MongoDB for type string '{modality_type_string}'"
                self.logger.log_error(error_msg)
                if log_import_error_func:
                    log_import_error_func(
                        import_id,
                        dataset_id,
                        "MODALITY_NOT_FOUND_IN_DATABASE",
                        error_msg,
                        modality_type_string
                    )
                return None

            # 5. Aktualizuj external_id jeśli pusty
            modality_doc = modalities[0]
            modality_id = str(modality_doc.get("id", ""))

            if not modality_doc.get("external_id"):
                self._update_external_id(modality_id, modality_type_string, dataset_id)

            self.logger.log_info(f"✅ Mapped modality_id: {modality_type_string} -> {modality_id}")
            return modality_id

        except Exception as e:
            error_msg = f"Error mapping modality '{modality_type_string}': {e}"
            self.logger.log_error(error_msg)
            if log_import_error_func:
                log_import_error_func(
                    import_id,
                    dataset_id,
                    "MODALITY_MAPPING_ERROR",
                    error_msg,
                    modality_type_string
                )
            return None

    def _update_external_id(self, modality_id: str, external_id_value: str, dataset_id: str):
        """
        Aktualizuj external_id w MongoDB.

        Args:
            modality_id (str): MongoDB ID modality
            external_id_value (str): Wartość external_id do ustawienia
            dataset_id (str): ID datasetu
        """
        from bson import ObjectId

        db = self.mongo_api_service.client[dataset_id]

        result = db[Collections.MODALITY.value].update_one(
            {"_id": ObjectId(modality_id)},
            {"$set": {"external_id": external_id_value}}
        )

        if result.modified_count > 0:
            print(f"✅ Updated external_id for modality {modality_id}")
        else:
            print(f"⚠️ Could not update external_id for modality {modality_id}")
