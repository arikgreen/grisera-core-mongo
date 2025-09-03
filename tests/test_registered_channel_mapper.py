"""
Testy jednostkowe dla RegisteredChannelJsonLdHelper
"""

import json
import pytest
from pathlib import Path

from data_operations.data_export.jsonld_export.helpers.registered_channel_mapper import RegisteredChannelJsonLdHelper


class TestRegisteredChannelJsonLdHelper:
    """Testy dla RegisteredChannelJsonLdHelper"""

    def setup_method(self):
        """Setup przed każdym testem"""
        self.helper = RegisteredChannelJsonLdHelper()
        self.fixtures_path = Path(__file__).parent / "fixtures" / "registered_channel"

    def _load_json_fixture(self, filename: str) -> dict:
        """Helper do ładowania plików JSON z fixtures"""
        fixture_path = self.fixtures_path / filename
        with open(fixture_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_map_registered_channel_with_nested_data(self):
        """Test mapowania RegisteredChannel z zagnieżdżonymi danymi z rzeczywistej bazy MongoDB"""
        # Załaduj dane testowe z plików
        mongodb_doc = self._load_json_fixture("mongodb_input.json")
        expected_structure = self._load_json_fixture("expected_output.json")

        # Wykonaj mapowanie
        result = self.helper.map_to_json(mongodb_doc)

        # Sprawdź podstawowe pola
        assert result["@id"] == "68b78de602c86d0842d2664c"
        
        # Sprawdź Channel
        assert "co:hasChannel" in result
        assert len(result["co:hasChannel"]) == 1
        channel = result["co:hasChannel"][0]
        assert channel["@id"] == "68b78dd502c86d0842d265ce"
        
        # Sprawdź RegisteredData
        assert "co:hasRegisteredData" in result
        assert len(result["co:hasRegisteredData"]) == 1
        registered_data = result["co:hasRegisteredData"][0]
        assert registered_data["@id"] == "68b78de502c86d0842d2661a"

        print("\n=== ACTUAL RESULT ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("\n=== EXPECTED STRUCTURE ===")
        print(json.dumps(expected_structure, indent=2, ensure_ascii=False))

    def test_map_registered_channel_without_nested_data(self):
        """Test mapowania RegisteredChannel bez zagnieżdżonych danych"""
        # Dane bez related fields
        mongodb_doc = {
            "_id": "68b78de602c86d0842d2664c",
            "external_id": ":rcP09UL",
            "channel_id": "68b78dd502c86d0842d265ce",
            "registered_data_id": "68b78de502c86d0842d2661a",
            "related_channels": [],
            "related_registered_data": []
        }

        # Wykonaj mapowanie
        result = self.helper.map_to_json(mongodb_doc)

        # Sprawdź podstawowe pola
        assert result["@id"] == "68b78de602c86d0842d2664c"
        
        # Sprawdź brak zagnieżdżonych danych
        assert "co:hasChannel" not in result
        assert "co:hasRegisteredData" not in result

    def test_entity_type(self):
        """Test zwracania typu encji"""
        assert self.helper._get_entity_type() == "RegisteredChannel"

    def test_collection_key(self):
        """Test zwracania klucza kolekcji JSON-LD"""
        assert self.helper.get_jsonld_collection_key() == "co:RegisteredChannel"

    def test_collection_enum(self):
        """Test zwracania enum kolekcji"""
        from mongo_service.collection_mapping import Collections
        assert self.helper.get_collection_enum() == Collections.REGISTERED_CHANNEL


if __name__ == "__main__":
    pytest.main([__file__])