from typing import Optional, Callable
import re

from mongo_service.collection_mapping import Collections


class LifeActivityTypeMapper:
    """
    Mapuje stringi typu aktywności życiowej (np. 'co:lifeActivityMovement')
    na MongoDB ID, z automatyczną aktualizacją external_id gdy pusty.
    """

    def __init__(self, mongo_api_service, logger):
        self.mongo_api_service = mongo_api_service
        self.logger = logger

    def _camel_case_to_snake_case(self, camel_case: str) -> str:
        """
        Konwertuj CamelCase na snake_case.
        Movement -> movement
        HeartActivity -> heart_activity
        """
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_case)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def map_to_mongodb_id(
        self,
        life_activity_type_string: str,
        dataset_id: str,
        import_id: str = None,
        log_import_error_func: Optional[Callable] = None
    ) -> Optional[str]:
        """
        Mapuje string typu aktywności życiowej na MongoDB ID.
        co:lifeActivityMovement -> szukaj "movement" -> zwróć MongoDB ID
        Aktualizuje external_id jeśli pusty.

        Args:
            life_activity_type_string (str): String z JSON-a (np. 'co:lifeActivityMovement')
            dataset_id (str): ID datasetu
            import_id (str): ID importu (opcjonalne, do logowania)
            log_import_error_func (Callable): Funkcja do logowania błędów importu

        Returns:
            Optional[str]: MongoDB ID life_activity lub None
        """
        from grisera.life_activity.life_activity_model import LifeActivity

        try:
            # 1. Wyciągnij część po ':' i usuń 'lifeActivity'
            type_part = life_activity_type_string.split(':')[-1]
            if type_part.lower().startswith('lifeactivity'):
                normalized = type_part[12:]
            else:
                normalized = type_part

            # 2. CamelCase -> snake_case
            snake_case_name = self._camel_case_to_snake_case(normalized)

            # 3. Szukaj w enum LifeActivity
            matching_life_activity = None
            for life_activity in LifeActivity:
                if life_activity.name == snake_case_name:
                    matching_life_activity = life_activity
                    break

            if not matching_life_activity:
                error_msg = f"Could not match life activity type '{life_activity_type_string}' to any known LifeActivity enum value"
                self.logger.log_error(error_msg)
                if log_import_error_func:
                    log_import_error_func(
                        import_id,
                        dataset_id,
                        "LIFE_ACTIVITY_TYPE_NOT_FOUND",
                        error_msg,
                        life_activity_type_string
                    )
                return None

            # 4. Szukaj w MongoDB
            life_activity_value = matching_life_activity.value
            query = {"life_activity": life_activity_value}
            life_activities = self.mongo_api_service.get_documents(
                collection_name=Collections.LIFE_ACTIVITY.value,
                dataset_id=dataset_id,
                query=query
            )

            if not life_activities:
                error_msg = f"LifeActivity '{life_activity_value}' not found in MongoDB for type string '{life_activity_type_string}'"
                self.logger.log_error(error_msg)
                if log_import_error_func:
                    log_import_error_func(
                        import_id,
                        dataset_id,
                        "LIFE_ACTIVITY_NOT_FOUND_IN_DATABASE",
                        error_msg,
                        life_activity_type_string
                    )
                return None

            # 5. Aktualizuj external_id jeśli pusty
            life_activity_doc = life_activities[0]
            life_activity_id = str(life_activity_doc.get("id", ""))

            if not life_activity_doc.get("external_id"):
                self._update_external_id(life_activity_id, life_activity_type_string, dataset_id)

            self.logger.log_info(f"✅ Mapped life_activity_id: {life_activity_type_string} -> {life_activity_id}")
            return life_activity_id

        except Exception as e:
            error_msg = f"Error mapping life activity '{life_activity_type_string}': {e}"
            self.logger.log_error(error_msg)
            if log_import_error_func:
                log_import_error_func(
                    import_id,
                    dataset_id,
                    "LIFE_ACTIVITY_MAPPING_ERROR",
                    error_msg,
                    life_activity_type_string
                )
            return None

    def _update_external_id(self, life_activity_id: str, external_id_value: str, dataset_id: str):
        """
        Aktualizuj external_id w MongoDB.

        Args:
            life_activity_id (str): MongoDB ID life_activity
            external_id_value (str): Wartość external_id do ustawienia
            dataset_id (str): ID datasetu
        """
        from bson import ObjectId

        db = self.mongo_api_service.client[dataset_id]

        result = db[Collections.LIFE_ACTIVITY.value].update_one(
            {"_id": ObjectId(life_activity_id)},
            {"$set": {"external_id": external_id_value}}
        )

        if result.modified_count > 0:
            print(f"✅ Updated external_id for life_activity {life_activity_id}")
        else:
            print(f"⚠️ Could not update external_id for life_activity {life_activity_id}")
