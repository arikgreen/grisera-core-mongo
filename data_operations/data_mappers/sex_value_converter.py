from data_operations.import_logger import get_import_logger
from data_operations.utils import remove_prefix


def map_sex_value(raw_sex_value: str) -> str:
    """Maps sex values from ontology format to standard values"""
    if not raw_sex_value:
        return raw_sex_value

    # Remove prefix if exists
    clean_value = remove_prefix(raw_sex_value)

    # Value mapping (case-insensitive)
    sex_mapping = {
        "sexmale": "Male",
        "sexfemale": "Female",
        "m": "Male",
        "f": "Female"
    }

    mapped_value = sex_mapping.get(clean_value.lower(), clean_value)

    if mapped_value != raw_sex_value:
        get_import_logger().log_mapping("Participant", "sex", raw_sex_value, mapped_value)

    return mapped_value
