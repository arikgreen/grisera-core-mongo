import base64
import re


def decode_file_content(file_content: str) -> str:
    """Dekoduje zawartość pliku z base64 jeśli potrzeba"""
    print("🔓 Decoding file content...")
    if file_content.startswith('data:'):
        print("📄 Detected base64 encoded data, decoding...")
        # Handle base64 encoded data
        data_part = file_content.split(',')[1]
        decoded = base64.b64decode(data_part).decode('utf-8')
        print(f"✅ Base64 decoded. Size: {len(decoded)} characters")
        return decoded
    else:
        print("📄 Using plain text content")
        return file_content


def remove_prefix(entity_name: str) -> str:
    """Usuwa przedrostki typu co:, pc:, owl: z nazwy encji"""
    if ':' in entity_name:
        clean_name = entity_name.split(':', 1)[1]
        return clean_name
    return entity_name


def normalize_property_name(prop_name: str) -> str:
    """Normalizuje nazwę właściwości (usuwa prefiks, camelCase->snake_case)"""
    # Usuń prefiks
    normalized = remove_prefix(prop_name)
    
    # Konwersja camelCase na snake_case
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', normalized)
    result = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    if result != prop_name:
        print(f"🔄 Property normalized: {prop_name} -> {result}")
    
    return result