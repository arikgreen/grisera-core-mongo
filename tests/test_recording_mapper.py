"""
Testy jednostkowe dla RecordingJsonLdHelper
"""

import json
import pytest
from pathlib import Path

from data_operations.data_export.jsonld_export.helpers.recording_mapper import RecordingJsonLdHelper


class TestRecordingJsonLdHelper:
    """Testy dla RecordingJsonLdHelper"""

    def setup_method(self):
        """Setup przed każdym testem"""
        self.helper = RecordingJsonLdHelper()
        self.fixtures_path = Path(__file__).parent / "fixtures" / "recording"

    def _load_json_fixture(self, filename: str) -> dict:
        """Helper do ładowania plików JSON z fixtures"""
        fixture_path = self.fixtures_path / filename
        with open(fixture_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_map_recording_with_nested_data(self):
        """Test mapowania Recording z zagnieżdżonymi danymi z rzeczywistej bazy MongoDB"""
        # Załaduj dane testowe z plików
        mongodb_doc = self._load_json_fixture("mongodb_input.json")
        expected_structure = self._load_json_fixture("expected_output.json")

        # Wykonaj mapowanie
        result = self.helper.map_to_json(mongodb_doc)

        # Sprawdź podstawowe pola
        assert result["@id"] == "68b752efa4ca959ee0715c67"
        
        # Sprawdź RegisteredChannel
        assert "co:hasRegisteredChannel" in result
        assert len(result["co:hasRegisteredChannel"]) == 1
        reg_channel = result["co:hasRegisteredChannel"][0]
        assert reg_channel["@id"] == "68b752efa4ca959ee0715c66"
        
        # Sprawdź RegisteredData
        assert "co:hasRegisteredData" in reg_channel
        assert len(reg_channel["co:hasRegisteredData"]) == 1
        assert reg_channel["co:hasRegisteredData"][0]["@id"] == "68b752efa4ca959ee0715c65"
        
        # Sprawdź Channel
        assert "co:hasChannel" in reg_channel
        assert reg_channel["co:hasChannel"][0]["@id"] == "co:channelAudio"
        
        # Sprawdź Participation
        assert "co:hasParticipation" in result
        assert len(result["co:hasParticipation"]) == 1
        participation = result["co:hasParticipation"][0]
        assert participation["@id"] == "68b752d9a4ca959ee0715c64"
        
        # Sprawdź Properties
        assert "pc:hasProperty" in result
        assert len(result["pc:hasProperty"]) == 1
        prop = result["pc:hasProperty"][0]
        assert prop["pc:hasKey"] == "cameraLocation"
        assert prop["pc:hasValue"] == "UL"

        print("\\n=== ACTUAL RESULT ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("\\n=== EXPECTED STRUCTURE ===")
        print(json.dumps(expected_structure, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    pytest.main([__file__])