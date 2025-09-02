"""
Testy jednostkowe dla TimeSeriesJsonLdHelper
"""

import json
import pytest
from pathlib import Path

from data_operations.data_export.jsonld_export.helpers.time_series_mapper import TimeSeriesJsonLdHelper


class TestTimeSeriesJsonLdHelper:
    """Testy dla TimeSeriesJsonLdHelper"""

    def setup_method(self):
        """Setup przed każdym testem"""
        self.helper = TimeSeriesJsonLdHelper()
        self.fixtures_path = Path(__file__).parent / "fixtures" / "time_series"

    def _load_json_fixture(self, filename: str) -> dict:
        """Helper do ładowania plików JSON z fixtures"""
        fixture_path = self.fixtures_path / filename
        with open(fixture_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_map_time_series_with_nested_data(self):
        """Test mapowania TimeSeries z zagnieżdżonymi danymi z rzeczywistej bazy MongoDB"""
        # Załaduj dane testowe z plików
        mongodb_doc = self._load_json_fixture("mongodb_input.json")
        expected_structure = self._load_json_fixture("expected_output.json")

        # Wykonaj mapowanie
        result = self.helper.map_to_json(mongodb_doc)

        # Sprawdź podstawowe pola
        assert result["@id"] == "68b6dc6379acd6b915b0e17e"
        assert result["co:hasTimestamp"] == "1970-01-01 00:00:01"
        assert result["co:hasValue"] == 1
        assert result["co:timeSeriesSource"] == "6044242f-f69b-4954-ae20-72e4bc10768a/test.png"
        
        # Sprawdź properties
        assert "pc:hasProperty" in result
        assert len(result["pc:hasProperty"]) == 1
        assert result["pc:hasProperty"][0]["pc:hasKey"] == "spacing"
        assert result["pc:hasProperty"][0]["pc:hasValue"] == "Irregular"
        
        # Sprawdź ObservableInformation
        assert "co:hasObservableInformation" in result
        assert len(result["co:hasObservableInformation"]) == 1
        obs_info = result["co:hasObservableInformation"][0]
        assert obs_info["@id"] == "68b6dc6379acd6b915b0e17c"
        
        # Sprawdź Measures
        assert "co:hasMeasure" in result
        assert len(result["co:hasMeasure"]) == 1
        measure = result["co:hasMeasure"][0]
        assert measure["@id"] == "68b6dbec79acd6b915b0e15a"
        assert measure["co:measureDatatype"] == "string"

        print("\\n=== ACTUAL RESULT ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("\\n=== EXPECTED STRUCTURE ===")
        print(json.dumps(expected_structure, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    pytest.main([__file__])
