import re
from typing import List, Optional, Union, Dict, Any

from mongo_service import MongoApiService
from mongo_service.collection_mapping import Collections
from grisera import SearchService, SearchOut, SearchResultItem


class SearchServiceMongoDB(SearchService):
    """
    Object to handle logic of search requests across MongoDB datasets and collections.

    Attributes:
        mongo_api_service (MongoApiService): Service used to communicate with Mongo API
    """

    # Definicja pól przeszukiwanych dla poszczególnych kolekcji
    COLLECTION_SEARCH_FIELDS: Dict[str, List[str]] = {
        "activities": [
            "external_id",
            "activity",
            "additional_properties.value",
            "activity_executions.additional_properties.value",
        ],
        "arrangements": ["external_id", "arrangement_type", "arrangement_distance"],
        "channels": ["external_id", "description", "type", "additional_properties.value"],
        "experiments": ["external_id", "experiment_name", "additional_properties.value"],
        # "file_operation_errors": ["message", "error", "file_name"],
        # "file_operations": ["file_name", "status", "operation_type"],
        "life_activities": ["external_id", "life_activity"],
        "measure_names": ["external_id", "name", "type"],
        "measures": ["external_id", "range", "unit", "values"],
        "modalities": ["external_id", "modality"],
        "participants": ["external_id", "name", "date_of_birth", "sex", "disorder", "participant_states.age"],
        # "participations": ["role", "notes", "description"],
        "recordings": ["external_id", "description", "path", "file_name"],
        # "registered_channels": ["channel_name", "external_id", "description"],
        # "registered_data": ["external_id", "description", "data_type"],
        "scenarios": ["external_id", "participant_id.value"],
    }

    # Zachowanie kompatybilności wstecznej dla listy kolekcji
    SUPPORTED_COLLECTIONS = list(COLLECTION_SEARCH_FIELDS.keys())

    def __init__(self):
        super().__init__()
        self.mongo_api_service = MongoApiService()

    def _format_match(self, key_label: str, full_value: str, match_obj: re.Match) -> str:
        """Formatuje wycinek tekstu wokół dopasowania."""
        start = max(0, match_obj.start() - 30)
        end = min(len(full_value), match_obj.end() + 30)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(full_value) else ""
        return f"[{key_label}] {prefix}{full_value[start:end]}{suffix}"

    def _get_document_display_name(self, doc: Dict[str, Any]) -> str:
        """Pobiera nazwę wyświetlaną dokumentu (z pól głównych lub z additional_properties)."""
        # 1. Sprawdzenie pól głównych
        for key in ("name", "title", "channel_name", "file_name", "activity"):
            if doc.get(key):
                return str(doc[key])

        # 2. Sprawdzenie additional_properties
        props = doc.get("additional_properties")
        if isinstance(props, list):
            for prop in props:
                if isinstance(prop, dict) and prop.get("key") == "name" and prop.get("value"):
                    return str(prop["value"])

        return doc.get("external_id") or "Match found"

    def _extract_snippet(self, doc: Dict[str, Any], search_term: str) -> str:
        """
        Przeszukuje dokument (w tym additional_properties i zagnieżdżone activity_executions)
        w celu znalezienia trafienia i wygenerowania wycinka.
        """
        search_pattern = re.compile(re.escape(search_term), re.IGNORECASE)

        # 1. Przeszukanie głównej tablicy additional_properties
        props = doc.get("additional_properties")
        if isinstance(props, list):
            for prop in props:
                if isinstance(prop, dict):
                    val = str(prop.get("value") or "")
                    match = search_pattern.search(val)
                    if match:
                        key_name = prop.get("key", "property")
                        return self._format_match(key_name, val, match)

        # 2. Przeszukanie zagnieżdżonych executions (np. activity_executions)
        executions = doc.get("activity_executions")
        if isinstance(executions, list):
            for exec_item in executions:
                if isinstance(exec_item, dict):
                    exec_props = exec_item.get("additional_properties", [])
                    if isinstance(exec_props, list):
                        for prop in exec_props:
                            if isinstance(prop, dict):
                                val = str(prop.get("value") or "")
                                match = search_pattern.search(val)
                                if match:
                                    key_name = prop.get("key", "property")
                                    return self._format_match(f"execution.{key_name}", val, match)

        # 3. Przeszukanie pozostałych pól tekstowych na poziomie głównym
        for field, value in doc.items():
            if field in ("_id", "additional_properties", "activity_executions") or not isinstance(value, str):
                continue
            match = search_pattern.search(value)
            if match:
                return self._format_match(field, value, match)

        return self._get_document_display_name(doc)

    def search_text_in_datasets(
        self,
        dataset_ids: List[Union[int, str]],
        collections: Optional[List[str]],
        text: Optional[str],
        page: int = 1,
        limit: int = 10,
    ) -> SearchOut:
        """
        Search text across multiple MongoDB databases (datasets) and configured collection fields.
        """
        if not dataset_ids:
            return SearchOut(total=0, page=page, limit=limit, results=[])

        target_collections = (
            [c for c in collections if c in self.COLLECTION_SEARCH_FIELDS]
            if collections
            else self.SUPPORTED_COLLECTIONS
        )

        all_matches: List[SearchResultItem] = []
        is_text_search = bool(text and text.strip())
        escaped_q = re.escape(text.strip()) if is_text_search else ""

        for dataset_id in dataset_ids:
            db = self.mongo_api_service.client[str(dataset_id)]

            for coll_name in target_collections:
                searchable_fields = self.COLLECTION_SEARCH_FIELDS.get(
                    coll_name, ["name", "description", "additional_properties.value"]
                )

                # Budowanie kwerendy z uwzględnieniem dot-paths
                query = {}
                if is_text_search:
                    query["$or"] = [
                        {field: {"$regex": escaped_q, "$options": "i"}}
                        for field in searchable_fields
                    ]

                collection = db[coll_name]
                cursor = collection.find(query)

                for doc in cursor:
                    snippet = (
                        self._extract_snippet(doc, text)
                        if is_text_search
                        else self._get_document_display_name(doc)
                    )

                    all_matches.append(
                        SearchResultItem(
                            id=str(doc.get("_id")),
                            dataset_id=str(dataset_id),
                            collection=coll_name,
                            snippet=snippet,
                        )
                    )

        total_count = len(all_matches)

        # Paginacja wyników
        skip = (page - 1) * limit
        paginated_results = all_matches[skip : skip + limit]

        return SearchOut(
            total=total_count,
            page=page,
            limit=limit,
            results=paginated_results,
        )
