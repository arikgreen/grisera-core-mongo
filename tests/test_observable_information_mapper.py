"""
Testy jednostkowe dla ObservableInformationJsonLdHelper
"""

import json
import pytest
from pathlib import Path

from data_operations.data_export.jsonld_export.helpers.observable_information_mapper import ObservableInformationJsonLdHelper


class TestObservableInformationJsonLdHelper:
    """Testy dla ObservableInformationJsonLdHelper"""

    def setup_method(self):
        """Setup przed każdym testem"""
        self.helper = ObservableInformationJsonLdHelper()
        self.fixtures_path = Path(__file__).parent / "fixtures" / "observable_information"

    def _load_json_fixture(self, filename: str) -> dict:
        """Helper do ładowania plików JSON z fixtures"""
        fixture_path = self.fixtures_path / filename
        with open(fixture_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_map_observable_information_with_nested_data(self):
        """Test mapowania ObservableInformation z zagnieżdżonymi danymi z rzeczywistej bazy MongoDB"""
        # Załaduj dane testowe z plików (będą dostępne po pokazaniu struktury DB)
        # mongodb_doc = self._load_json_fixture("mongodb_input.json")
        # expected_structure = self._load_json_fixture("expected_output.json")

        # Tymczasowe dane testowe
        mongodb_doc = {
            "id": "68b75329a4ca959ee0715c68",
            "modality_id": "68b7524fa4ca959ee0715c2f",
            "life_activity_id": "68b7524fa4ca959ee0715c3e",
            "_parent_recording": {
                "_id": "68b752efa4ca959ee0715c67",
                "participation_id": "68b752d9a4ca959ee0715c64",
                "registered_channel_id": "68b752efa4ca959ee0715c66"
            },
            "related_participations": [],
            "related_participants": [],
            "related_time_series": [],
            "related_modalities": [],
            "related_life_activities": [],
            "related_activity_executions": [],
            "related_activities": []
        }

        # Wykonaj mapowanie
        result = self.helper.map_to_json(mongodb_doc)

        # Sprawdź podstawowe pola
        assert result["@id"] == "68b75329a4ca959ee0715c68"
        
        # Sprawdź Recording
        assert "co:hasRecording" in result
        assert len(result["co:hasRecording"]) == 1
        recording = result["co:hasRecording"][0]
        assert recording["@id"] == "68b752efa4ca959ee0715c67"
        
        # Sprawdź Modality
        assert "co:hasModality" in result
        assert result["co:hasModality"][0]["@id"] == "68b7524fa4ca959ee0715c2f"
        
        # Sprawdź LifeActivity
        assert "co:hasLifeActivity" in result
        assert result["co:hasLifeActivity"][0]["@id"] == "68b7524fa4ca959ee0715c3e"

        print("\\n=== ACTUAL RESULT ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    pytest.main([__file__])