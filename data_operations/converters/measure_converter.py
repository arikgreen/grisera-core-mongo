from typing import Dict, Any, Optional
from grisera import MeasureIn, MeasureNameIn, PropertyIn
from .base import BaseEntityConverter, DEBUG
from .measure_name_converter import MeasureNameConverter
from data_operations.utils import remove_prefix
from mongo_service.collection_mapping import Collections
from services.mongo_services import MongoServiceFactory


class MeasureConverter(BaseEntityConverter[MeasureIn]):
    JSON_KEY_CANDIDATES_FOR_DATATYPE = ["measureDatatype", "hasDatatype", "datatype"]
    JSON_KEY_CANDIDATES_FOR_RANGE = ["measureRange", "hasRange", "range"]
    JSON_KEY_CANDIDATES_FOR_UNIT = ["measureUnit", "hasUnit", "unit"]
    JSON_KEY_CANDIDATES_FOR_MEASURE_NAME_ID = ["hasMeasureName", "measure_name_id", "measureNameId"]
    JSON_KEY_CANDIDATES_FOR_MEASURE_NAME = ["hasName", "name"]
    DEFAULT_MAIN_FIELD_PREFIX = "Measure"
    
    
    def __init__(self, import_id: str):
        super().__init__(import_id)
        self.measure_name_service = MeasureNameConverter(import_id)

    
    def convert(self, json_entity: Dict[str, Any]) -> MeasureIn:
        external_id = self._get_external_id(json_entity)

        # Wyciągnij datatype - pole wymagane
        datatype = self._get_optional_field_value(
            json_entity,
            self.JSON_KEY_CANDIDATES_FOR_DATATYPE
        )
        
        # Wyciągnij range - pole wymagane
        range_value = self._get_optional_field_value(
            json_entity,
            self.JSON_KEY_CANDIDATES_FOR_RANGE
        )
        
        # Wyciągnij unit - pole wymagane, ale może nie być w JSON
        unit = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_UNIT)
        if not unit:
            unit = "unknown"  # domyślna wartość
        
        # Wyciągnij measure_name_id z zagnieżdżonej struktury co:hasMeasureName
        measure_name_id = self._extract_measure_name_id_from_json(json_entity)
        
        measure = MeasureIn(
            datatype=datatype,
            range=range_value,
            unit=unit,
            measure_name_id=measure_name_id
        )

        additional_properties = self._set_common_properties(json_entity, measure)

        processed_clean_keys = []
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_DATATYPE)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_RANGE)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_UNIT)
        processed_clean_keys.extend(self.JSON_KEY_CANDIDATES_FOR_MEASURE_NAME_ID)
        self._add_remaining_properties(json_entity, additional_properties, processed_clean_keys)

        clean_name_for_log = remove_prefix(external_id) if external_id else "Unknown"
        if DEBUG:
            print(f"📝 Creating MeasureIn: name='{clean_name_for_log}', datatype='{datatype}', range='{range_value}', unit='{unit}', measure_name_id='{measure_name_id}', external_id='{measure.external_id}', import_job_id='{measure.import_job_id}', properties={len(additional_properties)} (including common)")

        return measure

    def _extract_measure_name_from_json(self, json_entity: Dict[str, Any]) -> Optional[str]:
        """
        Wyciąga nazwę measure z zagnieżdżonego obiektu hasMeasureName.
        Zwraca nazwę measure (np. "Familiarity") z pola hasName.
        """
        # Sprawdź co:hasMeasureName (zagnieżdżony obiekt)
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_MEASURE_NAME_ID:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    # To jest hasMeasureName - wyciągnij hasName
                    if isinstance(entity_value, list) and len(entity_value) > 0:
                        # Jeśli to lista, weź pierwszy element
                        measure_name_obj = entity_value[0]
                        if isinstance(measure_name_obj, dict) and "hasName" in measure_name_obj:
                            measure_name = measure_name_obj["hasName"]
                            if DEBUG:
                                print(f"✅ Found MeasureName from {entity_key_with_prefix}: {measure_name}")
                            return measure_name
                    elif isinstance(entity_value, dict) and "hasName" in entity_value:
                        # Jeśli to pojedynczy obiekt
                        measure_name = entity_value["hasName"]
                        if DEBUG:
                            print(f"✅ Found MeasureName from {entity_key_with_prefix}: {measure_name}")
                        return measure_name

        if DEBUG:
            print("⚠️ No MeasureName found in Measure")
        return None

    def _extract_measure_name_id_from_json(self, json_entity: Dict[str, Any]) -> Optional[str]:
        """
        Wyciąga MeasureName ID z JSON z zagnieżdżonej struktury co:hasMeasureName.
        Zwraca source ID który będzie mapowany na MongoDB ID później.
        """
        # Najpierw sprawdź proste przypadki
        simple_mn_id = self._get_optional_field_value(json_entity, self.JSON_KEY_CANDIDATES_FOR_MEASURE_NAME_ID)
        if simple_mn_id:
            if DEBUG:
                print(f"✅ Found simple measure_name_id: {simple_mn_id}")
            return simple_mn_id
        
        # Następnie sprawdź co:hasMeasureName (zagnieżdżony obiekt)
        for clean_candidate_key in self.JSON_KEY_CANDIDATES_FOR_MEASURE_NAME_ID:
            for entity_key_with_prefix, entity_value in json_entity.items():
                if remove_prefix(entity_key_with_prefix) == clean_candidate_key:
                    # To jest hasMeasureName - wyciągnij @id MeasureName
                    measure_name_id = self._extract_nested_entity_id(entity_value)
                    if measure_name_id:
                        if DEBUG:
                            print(f"✅ Found MeasureName source ID from {entity_key_with_prefix}: {measure_name_id}")
                        # Zapisujemy source ID - mapowanie na MongoDB ID zostanie zrobione później
                        return measure_name_id
        
        if DEBUG:
            print("⚠️ No MeasureName reference found in Measure")
        return None

    def save(self, json_entity: Dict[str, Any], dataset_id: str, import_id: str): # -> MeasureIn:
        """
        Konwertuje i zapisuje Measure.
        """
        return self._save_measure_with_mapping(self.convert(json_entity), dataset_id, import_id, self._extract_measure_name_from_json(json_entity))

    def find_by_source_id(self, source_id: str, dataset_id: str) -> str:
        return self._find_by_source_id(source_id, dataset_id, Collections.MEASURE)

    
    def _save_measure_with_mapping(self, grisera_object, dataset_id: str, import_id: str, clean_name: str = None) -> Optional[MeasureIn]:
        """
        Zapisuje Measure z mapowaniem measure_name_id z source ID na MongoDB ID.
        """
        try:
            if DEBUG:
                print(f"💾 Saving Measure with measure_name_id mapping...")

            measure_name_source_id = str(grisera_object.measure_name_id)
            measure_name_mongo_id = self._find_by_source_id(measure_name_source_id, dataset_id, Collections.MEASURE_NAME)

            if measure_name_mongo_id:
                mapped_measure_name_id = measure_name_mongo_id
                if DEBUG:
                    print(f"✅ Mapped measure_name_id: {grisera_object.measure_name_id} -> {measure_name_mongo_id}")
            else:
                measure_name_mongo_id = self._find_or_create_measure_name_by_name(measure_name_source_id, dataset_id, import_id, clean_name
                )

                if measure_name_mongo_id:
                    mapped_measure_name_id = measure_name_mongo_id
                    if DEBUG:
                        print(
                            f"✅ Found/created MeasureName by name: {measure_name_source_id} -> {measure_name_mongo_id}")
                else:
                    print(f"❌ Could not find or create MeasureName for: {measure_name_source_id}")
                    print(f"❌ Cannot save Measure without valid measure_name_id")
                    print(f"❌ Import error: Cannot save Measure without valid measure_name_id for {str(grisera_object.measure_name_id)}")
                    return None

            grisera_object.measure_name_id = mapped_measure_name_id

            # KROK 3: Zapisz Measure używając serwisu
            if DEBUG:
                print(f"✅ Measure being saved with final data: {grisera_object.__dict__}")
            result = self.services.get_measure_service().save_measure(grisera_object, dataset_id)
            saved_measure_id = str(getattr(result, 'id', 'unknown'))
            if DEBUG:
                print(f"✅ Measure saved with MongoDB ID: {saved_measure_id}")

            # KROK 4: Loguj mapowanie dla debugowania
            if mapped_measure_name_id != grisera_object.measure_name_id:
                if DEBUG:
                    print(
                        f"🔗 Final measure_name_id mapping: {grisera_object.measure_name_id} -> {mapped_measure_name_id}")

            return result

        except Exception as e:
            print(f"❌ Error saving Measure with mapping: {e}")
            raise e
    def _find_or_create_measure_name_by_name(self, measure_name_source_id: str, dataset_id: str,
                                             import_id: str, clean_name_ex: str) -> str:
        """
        Znajduje MeasureName po nazwie (case-insensitive) lub tworzy nowy.

        Args:
            measure_name_source_id: ID z JSON (np. "fear", "http://...#fear")
            dataset_id: ID datasetu
            import_id: ID procesu importu

        Returns:
            MongoDB ID dla MeasureName lub None jeśli nie udało się utworzyć
        """
        try:
            clean_name = clean_name_ex if clean_name_ex else self._extract_clean_measure_name(measure_name_source_id)
            if DEBUG:
                print(
                    f"🔍 Searching for MeasureName with clean name: '{clean_name}' (from source: '{measure_name_source_id}')")

            # 1. Najpierw sprawdź czy istnieje MeasureName z podobną nazwą (case-insensitive)
            existing_measure_name_id = self._find_existing_measure_name_by_name(clean_name, dataset_id)
            if existing_measure_name_id:
                # Zaktualizuj external_id w istniejącym MeasureName
                self._update_measure_name_external_id(existing_measure_name_id, measure_name_source_id, dataset_id)
                return existing_measure_name_id

            # 2. Jeśli nie znaleziono, utwórz nowy MeasureName
            if DEBUG:
                print(f"📝 Creating new MeasureName for: '{clean_name}'")
            return self._create_new_measure_name_and_measure(clean_name, measure_name_source_id, dataset_id,
                                                             import_id)

        except Exception as e:
            print(f"❌ Error in _find_or_create_measure_name_by_name: {e}")
            return ""

    @staticmethod
    def _extract_clean_measure_name(source_id: str) -> str:
        """
        Wyciąga czystą nazwę measure z różnych formatów source_id.

        Przykłady:
        - "fear" -> "fear"
        - "http://www.semanticweb.org/GRISERA/contextualOntology/models/emotionalMeasures/ekman#fear" -> "fear"
        - "ekman:fear" -> "fear"
        """
        if not source_id:
            return "unknown"

        # Usuń prefix ":"
        clean_id = source_id.replace(":", "") if source_id.startswith(":") else source_id

        # Jeśli to URL, wyciągnij część po ostatnim # lub /
        if "http" in clean_id or "/" in clean_id:
            if "#" in clean_id:
                clean_id = clean_id.split("#")[-1]
            elif "/" in clean_id:
                clean_id = clean_id.split("/")[-1]

        # Usuń namespace prefixes (np. "ekman:fear" -> "fear")
        if ":" in clean_id:
            clean_id = clean_id.split(":")[-1]

        return clean_id.strip().lower()

    def _find_existing_measure_name_by_name(self, clean_name: str, dataset_id: str) -> str:
        """
        Znajduje istniejący MeasureName po nazwie (case-insensitive, zawieranie).
        """
        try:
            # Sprawdź czy nazwa jest zawarta w istniejących measure_names
            query_filter = {
                "name": {"$regex": f".*{clean_name}.*", "$options": "i"}
            }

            measure_names = self.mongo_api_service.get_documents(
                collection_name=Collections.MEASURE_NAME.value,
                dataset_id=dataset_id,
                query=query_filter
            )

            if measure_names and len(measure_names) > 0:
                # Preferuj dokładne dopasowanie
                for mn in measure_names:
                    if mn.get("name", "").lower() == clean_name:
                        if DEBUG:
                            print(f"✅ Found exact match for '{clean_name}': {mn.get('name')} (ID: {mn.get('id')})")
                        return str(mn.get("id", ""))

                # JeŚli nie ma dokładnego, weź pierwszy częściowy
                first_match = measure_names[0]
                if DEBUG:
                    print(
                        f"✅ Found partial match for '{clean_name}': {first_match.get('name')} (ID: {first_match.get('id')})")
                return str(first_match.get("id", ""))

            return ""

        except Exception as e:
            print(f"❌ Error finding existing MeasureName by name: {e}")
            return ""
        
    def _update_measure_name_external_id(self, measure_name_id: str, external_id: str, dataset_id: str):
        """
        Aktualizuje external_id w istniejącym MeasureName jeśli jest pusty.
        """
        try:
            measure_name_doc = self.mongo_api_service.get_document(
                measure_name_id,
                Collections.MEASURE_NAME.value,
                dataset_id
            )

            if measure_name_doc and not measure_name_doc.get("external_id"):
                measure_name_doc["external_id"] = f":{external_id}"

                self.mongo_api_service.update_document_with_dict(
                    collection_name=Collections.MEASURE_NAME.value,
                    id=measure_name_id,
                    new_document=measure_name_doc,
                    dataset_id=dataset_id
                )
                if DEBUG:
                    print(f"🔗 Updated MeasureName {measure_name_id} with external_id: :{external_id}")

        except Exception as e:
            print(f"❌ Error updating MeasureName external_id: {e}")

    def _create_new_measure_name_and_measure(self, clean_name: str, source_id: str, dataset_id: str,
                                             import_id: str) -> str:
        """
        Tworzy nowy MeasureName i odpowiadający mu domyślny Measure.

        Returns:
            MongoDB ID nowego MeasureName
        """
        try:
            # 1. Utwórz MeasureName
            measure_name_in = MeasureNameIn(
                name=clean_name.title(),  # Kapitalizuj pierwszą literę
                type="User defined",
                external_id=f":{source_id}",
                import_job_id=import_id,
                additional_properties=[
                    PropertyIn(key="auto_created", value="true"),
                    PropertyIn(key="source_id", value=source_id),
                    PropertyIn(key="import_job_id", value=import_id)
                ]
            )

            measure_name_service = self.services.get_measure_name_service()
            measure_name_result = measure_name_service.save_measure_name(measure_name_in, dataset_id)

            if hasattr(measure_name_result, 'errors') and measure_name_result.errors:
                print(f"❌ Error creating MeasureName: {measure_name_result.errors}")
                return ""

            measure_name_id = str(measure_name_result.id)
            if DEBUG:
                print(f"✅ Created new MeasureName: '{clean_name}' with ID: {measure_name_id}")

            # 2. Utwórz domyślny Measure dla tego MeasureName
            self._create_default_measure_for_measure_name(measure_name_id, source_id, dataset_id, import_id)

            return measure_name_id

        except Exception as e:
            print(f"❌ Error creating new MeasureName and Measure: {e}")
            return ""

    def _create_default_measure_for_measure_name(self, measure_name_id: str, source_id: str, dataset_id: str,
                                                 import_id: str):
        """
        Tworzy domyślny Measure dla nowo utworzonego MeasureName.
        """
        try:
            default_measure_in = MeasureIn(
                datatype="float",
                range="0-1",
                unit="normalized",
                measure_name_id=measure_name_id,
                external_id=source_id,
                import_job_id=import_id,
                additional_properties=[
                    PropertyIn(key="auto_created", value="true"),
                    PropertyIn(key="measure_name_id", value=measure_name_id),
                    PropertyIn(key="import_job_id", value=import_id)
                ]
            )

            measure_service = self.services.get_measure_service()
            measure_result = measure_service.save_measure(default_measure_in, dataset_id)

            if hasattr(measure_result, 'errors') and measure_result.errors:
                print(f"❌ Error creating default Measure: {measure_result.errors}")
            else:
                measure_id = str(measure_result.id)
                if DEBUG:
                    print(f"✅ Created default Measure with ID: {measure_id} for MeasureName: {measure_name_id}")

        except Exception as e:
            print(f"❌ Error creating default Measure: {e}")