import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, TypeVar, Generic, Optional, Set
from datetime import datetime

from grisera import PropertyIn
from data_operations.import_logger import get_import_logger
from data_operations.utils import remove_prefix
from mongo_service.mongo_api_service import MongoApiService
from mongo_service.collection_mapping import Collections
from services.mongo_services import MongoServiceFactory
from data_operations.file_operations_service import FileOperationsStatusService

# Type variable dla generycznego typu GRISERA In
GriseraInType = TypeVar('GriseraInType')

DEBUG = True


class BaseEntityConverter(ABC, Generic[GriseraInType]):
    """
    Abstrakcyjna klasa bazowa dla konwerterów encji JSON na obiekty GRISERA.
    Zakłada, że `json_entity` może mieć klucze z prefiksami, a `remove_prefix` je usuwa.
    Klucze przekazywane w `*_key_candidates` powinny być "czystymi" kluczami (bez prefiksów).
    """

    def __init__(self, import_id: str):
        self.import_id = import_id
        self.mongo_api_service = MongoApiService()
        self.services = MongoServiceFactory()
        self.file_ops_service = FileOperationsStatusService()


    def _get_optional_field_value(
        self,
        json_entity: Dict[str, Any],
        key_candidates: List[str],  # Lista "czystych" kluczy
        perform_deep_lookup: bool = False  # Jeśli True, szuka również w zagnieżdżonych obiektach
    ) -> Optional[str]:
        """
        Wyszukuje pierwszą pasującą wartość w json_entity na podstawie listy potencjalnych "czystych" kluczy.
        Porównuje klucze po usunięciu prefiksów z kluczy encji JSON.
        Zwraca wartość jako string lub None, jeśli nie znaleziono lub wartość jest "pusta".
        IGNORUJE złożone typy (listy, słowniki) - są one przeznaczone dla properties, nie głównych pól.
        """
        for clean_candidate_key in key_candidates:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    # Upewnij się, że wartość nie jest pusta (None lub pusty string)
                    # NOWE: Ignoruj złożone typy (listy, słowniki) - nie powinny być używane jako główne pola
                    if entity_value is not None and entity_value != "" and isinstance(entity_value, (str, int, float, bool)):
                        return str(entity_value)

                    if perform_deep_lookup:
                        # Jeśli wartość jest złożona (np. obiekt lub lista), spróbuj wyciągnąć @id
                        nested_id = self._extract_nested_entity_id(entity_value)
                        if nested_id:
                            return nested_id
        return None

    def _get_main_field_value(
        self,
        json_entity: Dict[str, Any],
        json_key_candidates: List[str],  # Lista "czystych" kluczy
        default_prefix_for_fallback: str,  # Np. "Activity", używane gdy @id też nie ma
        entity_id_str_for_fallback: Optional[str] = None  # Oryginalne @id jako string (może mieć prefix)
    ) -> str:
        """
        Wyciąga główną wartość pola encji. Jeśli nie znajdzie wśród kandydatów,
        używa wartości @id encji jako fallback. Jeśli @id nie ma, tworzy placeholder.
        Zawsze zwraca string.
        """
        value = self._get_optional_field_value(json_entity, json_key_candidates)
        if value is not None:
            return value

        # Nie znaleziono wartości wśród kandydatów, użyj fallbacka.
        final_fallback_value: str
        # Domyślna wartość dla logowania, jeśli nie ma @id
        clean_entity_id_for_print = f"{default_prefix_for_fallback.lower()}_unknown_id"

        effective_clean_entity_id: Optional[str] = None
        # Spróbuj uzyskać czyste @id z przekazanego entity_id_str_for_fallback
        if entity_id_str_for_fallback:
            cleaned_id = remove_prefix(entity_id_str_for_fallback)
            if cleaned_id and cleaned_id != "": # Upewnij się, że po usunięciu prefixu coś zostało
                effective_clean_entity_id = cleaned_id

        # Jeśli nie z przekazanego, spróbuj z json_entity["@id"]
        if not effective_clean_entity_id and "@id" in json_entity:
            raw_id_from_entity = json_entity["@id"]
            if raw_id_from_entity is not None and raw_id_from_entity != "":
                cleaned_id = remove_prefix(str(raw_id_from_entity))
                if cleaned_id and cleaned_id != "":
                     effective_clean_entity_id = cleaned_id

        if effective_clean_entity_id:
            final_fallback_value = effective_clean_entity_id
            clean_entity_id_for_print = effective_clean_entity_id # Zaktualizuj dla logu
            print(f"⚠️ No main field found from candidates {json_key_candidates} for entity '{clean_entity_id_for_print}', using entity ID as fallback: {final_fallback_value}")
        else:
            final_fallback_value = f"{default_prefix_for_fallback}_id_placeholder" # Zmieniony placeholder
            print(f"⚠️ No main field found from candidates {json_key_candidates} AND no valid @id found for '{clean_entity_id_for_print}'. Using placeholder: {final_fallback_value}")

        return final_fallback_value

    def _set_common_properties(self, json_entity: Dict[str, Any], target_object: GriseraInType) -> List[PropertyIn]:
        """
        Ustawia standardowe metadane importu bezpośrednio na obiekcie docelowym
        i zwraca listę dodatkowych właściwości (bez common properties).
        `source_entity_ref` przechowuje oryginalne @id (z potencjalnym prefiksem).
        """
        source_entity_id = "unknown_source_id"
        if "@id" in json_entity and json_entity["@id"] is not None and json_entity["@id"] != "":
            source_entity_id = str(json_entity["@id"])

        missing_attributes = []
        model_class_name = target_object.__class__.__name__

        if hasattr(target_object, 'external_id'):
            target_object.external_id = source_entity_id
        else:
            missing_attributes.append('external_id')

        if hasattr(target_object, 'import_job_id'):
            target_object.import_job_id = str(self.import_id)
        else:
            missing_attributes.append('import_job_id')

        if hasattr(target_object, 'import_timestamp'):
            target_object.import_timestamp = datetime.utcnow()
        else:
            missing_attributes.append('import_timestamp')

        # Jeśli brakuje jakichś atrybutów, zaloguj to
        if missing_attributes:
            print(f"⚠️ Model {model_class_name} nie dziedziczy po ImportableModel! Brakujące atrybuty: {', '.join(missing_attributes)}")
            print(f"   Model nie będzie miał automatycznie ustawionych pól: external_id, import_job_id, import_timestamp")
            print(f"   Sugeruję naprawić to dodając 'ImportableModel' do listy dziedziczenia w klasie {model_class_name}")

        properties = [
            PropertyIn(key="source_entity_ref", value=source_entity_id),
        ]
        return properties

    def _get_external_id(self, json_entity: Dict[str, Any]) -> Optional[str]:
        """
        Wyciąga external_id z @id encji JSON.
        Zwraca oryginalny @id (z potencjalnym prefiksem) lub None jeśli nie ma @id.
        """
        if "@id" in json_entity and json_entity["@id"] is not None and json_entity["@id"] != "":
            return str(json_entity["@id"])
        return None

    def _add_remaining_properties(
        self,
        json_entity: Dict[str, Any],
        properties_list: List[PropertyIn],
        processed_clean_keys: Optional[List[str]] = None # Lista "czystych" kluczy, które już zostały użyte
    ):
        """
        Dodaje wszystkie pozostałe właściwości z JSON jako PropertyIn.
        Klucze specjalne (@id, @type, rdf:type) są domyślnie wykluczane.
        Dodatkowo wyklucza klucze z `processed_clean_keys`.
        Obsługuje wartości string, numeryczne, boolean oraz listy prostych typów.
        """
        default_excluded_clean_keys: Set[str] = {
            remove_prefix("@id"),
            remove_prefix("@type"),
            remove_prefix("rdf:type")
        }

        user_excluded_clean_keys = set(remove_prefix(k) for k in (processed_clean_keys or []))
        final_excluded_clean_keys = default_excluded_clean_keys.union(user_excluded_clean_keys)

        for entity_key_with_prefix, value in json_entity.items():
            clean_key = remove_prefix(entity_key_with_prefix)
            if clean_key not in final_excluded_clean_keys:
                if isinstance(value, (str, int, float, bool)):
                    properties_list.append(PropertyIn(key=clean_key, value=str(value)))
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, (str, int, float, bool)):
                            properties_list.append(PropertyIn(key=clean_key, value=str(item)))

    def _extract_nested_entity_id(self, entity_value: Any) -> Optional[str]:
        """
        Wyciąga @id z zagnieżdżonych obiektów JSON (lista obiektów lub pojedynczy obiekt).
        """
        if isinstance(entity_value, list) and len(entity_value) > 0:
            # Lista obiektów - bierz pierwszy
            first_entity = entity_value[0]
            if isinstance(first_entity, dict) and "@id" in first_entity:
                return str(first_entity["@id"])
        elif isinstance(entity_value, dict) and "@id" in entity_value:
            # Pojedynczy obiekt
            return str(entity_value["@id"])
        elif isinstance(entity_value, str):
            # Proste ID jako string
            return entity_value

        return None

    @abstractmethod
    def convert(self, json_entity: Dict[str, Any]) -> GriseraInType:
        pass

    @abstractmethod
    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str) -> GriseraInType:
        pass


    @abstractmethod
    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        pass

    def _find_by_source_id(self, source_id: str, dataset_id: str, collection: Collections) -> str:
        """
        Uniwersalna metoda do znajdowania dokumentów po source_id
        """
        try:
            documents = self.mongo_api_service.get_documents(
                collection_name=collection.value,
                dataset_id=dataset_id,
                query={"external_id": source_id}
            )

            if documents:
                found_id = str(documents[0].get("id", ""))
                if DEBUG:
                    print(f"✅ Found {collection.value}: {source_id} -> MongoDB ID: {found_id}")
                return found_id

            if DEBUG:
                print(f"❌ {collection.value} not found for source_id: {source_id}")
            return ""

        except Exception as e:
            print(f"❌ Error finding {collection.value} by source_id {source_id}: {e}")
            return ""

    def _log_import_error(
            self,
            import_id: str,
            dataset_id: str,
            error_type: str,
            error_message: str,
            entity_str: str = None
    ):
        """
        Loguje błąd importu do bazy danych używając FileOperationsStatusService
        """
        self.file_ops_service.log_error(
            operation_uuid=import_id,
            dataset_id=dataset_id,
            error_type=error_type,
            error_message=error_message,
            entity_str=entity_str
        )