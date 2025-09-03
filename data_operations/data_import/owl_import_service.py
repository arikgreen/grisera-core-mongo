import json
from collections import defaultdict
from typing import Dict, Any

from rdflib import Graph, RDF, RDFS, URIRef

from data_operations.file_operations_model import FileOperationIn
from data_operations.utils import decode_file_content

DEBUG = True


class OwlImportService:
    """
    Serwis dedykowany do importu danych OWL.
    Konwertuje OWL na JSON i deleguje import do JsonImportService.
    """

    def __init__(self):
        from .json_import_service import JsonImportService  # Import lokalny aby uniknąć cyklicznych importów
        self.json_import_service = JsonImportService()

    def import_owl_data(self, import_data: FileOperationIn, import_id: str) -> int:
        """
        Importuje dane OWL poprzez konwersję na JSON i delegację do JsonImportService.
        Serwis wyżej zajmuje się async i error handling.

        Returns: liczba zaimportowanych rekordów
        """
        if DEBUG:
            print(f"📄 Starting OWL data import for import ID: {import_id}")

        # 1. Konwersja OWL → JSON
        json_data = self._convert_owl_to_json(decode_file_content(import_data.file_content))
        if DEBUG:
            print(f"✅ OWL converted to JSON: {len(json_data)} classes found")

        # 2. Przygotowanie danych dla JsonImportService
        # Convert to JSON string for processing
        json_content = json.dumps(json_data, ensure_ascii=False, indent=2)

        json_import_data = FileOperationIn(
            file_name=f"{import_data.file_name}_converted.json",
            file_type="application/json",
            file_content=json_content,  # This will be uploaded to MinIO automatically
            operation_type=import_data.operation_type,
            dataset_id=import_data.dataset_id,
            description=f"Converted from OWL: {import_data.description or import_data.file_name}",
            experiment_id=import_data.experiment_id,
            additional_data={
                "original_format": "owl",
                "original_filename": import_data.file_name,
                "converted_content_size": len(json_content),
                **(import_data.additional_data or {} if import_data.additional_data else {})
            }
        )
        if DEBUG:
            print(f"🔄 Delegating to JsonImportService...")
        imported_count = self.json_import_service.import_json_data(
            import_data=json_import_data,
            import_id=import_id
        )
        if DEBUG:
            print(f"✅ OWL import completed: {imported_count} records imported")
        return imported_count

    def _convert_owl_to_json(self, owl_content: str) -> Dict[str, Any]:
        """
            Konwertuje zawartość OWL na strukturę JSON
            """
        if DEBUG:
            print("🔄 Converting OWL to JSON structure...")

        if not owl_content or not owl_content.strip():
            raise ValueError("Empty OWL content provided")

        if not owl_content.strip().startswith('<?xml') and not owl_content.strip().startswith('<rdf:RDF'):
            if DEBUG:
                print(f"⚠️ Content doesn't start with XML declaration. First 100 chars: {owl_content[:100]}")
            raise ValueError("Content doesn't appear to be valid OWL/XML format")

        # Wczytaj graf
        g = Graph()
        try:
            g.parse(data=owl_content, format="xml")
            if DEBUG:
                print(f"✅ OWL graph parsed successfully. Graph size: {len(g)} triples")
        except Exception as e:
            if DEBUG:
                print(f"❌ Failed to parse OWL content: {str(e)}")
                print(f"🔍 Content preview: {owl_content[:200]}...")
            raise ValueError(f"Failed to parse OWL content: {str(e)}")

        # Pobierz przestrzenie nazw
        namespaces = self._get_namespaces(g)
        if DEBUG:
            print(f"🏷️ Found {len(namespaces)} namespaces: {list(namespaces.keys())}")

        # Znajdź wszystkie instancje klas
        instances = defaultdict(list)
        for s, p, o in g.triples((None, RDF.type, None)):
            if not isinstance(o, URIRef):
                continue
            # Skip owl:Ontology instances
            class_name = self._simplify(o, namespaces)
            if class_name == "owl:Ontology":
                continue
            instances[o].append(s)

        if DEBUG:
            print(f"🔍 Found {len(instances)} classes with instances:")
            for class_uri, resources in instances.items():
                class_name = self._simplify(class_uri, namespaces)
                print(f"  - {class_name}: {len(resources)} instances")

        # Buduj dane
        data = {}
        total_instances = 0
        for class_uri, resources in instances.items():
            class_name = self._simplify(class_uri, namespaces)
            data[class_name] = []

            if DEBUG and len(resources) > 0:
                print(f"🔨 Building structure for class {class_name} ({len(resources)} instances)")

            for resource in resources:
                structure = self._build_structure(g, resource, namespaces, set())
                data[class_name].append(structure)
                total_instances += 1

        if DEBUG:
            print(f"✅ Converted {len(data)} classes with {total_instances} total instances")
            for class_name, instances_list in data.items():
                print(f"  - {class_name}: {len(instances_list)} instances")

        return data

    def _simplify(self, uri, namespaces):
        """Upraszcza nazwę URI do prefiksu"""
        for prefix, ns in namespaces.items():
            if str(uri).startswith(str(ns)):
                return f"{prefix}:{str(uri).replace(str(ns), '')}"
        return str(uri)

    def _get_namespaces(self, graph):
        """Wydobywa wszystkie namespace'y"""
        namespaces = {}
        for prefix, ns in graph.namespaces():
            namespaces[prefix] = ns
        return namespaces

    def _build_structure(self, graph, resource, namespaces, visited):
        """Budowanie rekursywne struktury zagnieżdżonej"""
        if resource in visited:
            return {"@id": self._simplify(resource, namespaces)}  # Zapobiegamy cyklom

        visited.add(resource)
        node = {"@id": self._simplify(resource, namespaces)}

        for predicate, obj in graph.predicate_objects(subject=resource):
            pred = self._simplify(predicate, namespaces)
            
            # Skip rdf:type predicates to avoid unnecessary type information
            if pred == "rdf:type":
                continue

            if isinstance(obj, URIRef):
                node.setdefault(pred, [])
                node[pred].append(self._build_structure(graph, obj, namespaces, visited))
            else:
                node[pred] = str(obj)

        return node
