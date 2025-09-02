"""
TimeSeries JSON-LD Helper
"""
import json
from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class TimeSeriesJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji TimeSeries -> co:TimeSeries. Standardowe pobieranie z kolekcji."""
    
    def _get_entity_type(self) -> str:
        return "TimeSeries"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:TimeSeries"
    
    def get_collection_enum(self) -> Collections:
        return Collections.TIME_SERIES
    
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera TimeSeries dla dataset_id z zagnieżdżonymi elementami używając agregacji MongoDB.
        Pobiera powiązane ObservableInformation, Recordings, Participations i Participants.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        
        collection_name = self.get_collection_enum().value
        
        aggregation = [
            # Step 1: Convert observable_information_ids strings to ObjectIds for proper lookup
            {
                "$addFields": {
                    "metadata.observable_information_ids_objects": {
                        "$map": {
                            "input": "$metadata.observable_information_ids",
                            "as": "oid_string",
                            "in": {"$toObjectId": "$$oid_string"}
                        }
                    }
                }
            },
            
            # Step 2: Join with recordings through observable_informations
            {
                "$lookup": {
                    "from": "recordings",
                    "localField": "metadata.observable_information_ids_objects",
                    "foreignField": "observable_informations.id",
                    "as": "related_recordings"
                }
            },
            
            # Step 3: Join with participations through recording participation_id
            {
                "$lookup": {
                    "from": "participations",
                    "localField": "related_recordings.participation_id",
                    "foreignField": "_id",
                    "as": "related_participations"
                }
            },
            
            # Step 4: Join with participants through participation participant_state_id
            {
                "$lookup": {
                    "from": "participants",
                    "localField": "related_participations.participant_state_id", 
                    "foreignField": "participant_states.id",
                    "as": "related_participants"
                }
            },
            
            # Step 5: Join with observable_informations directly
            {
                "$lookup": {
                    "from": "observable_informations",
                    "localField": "metadata.observable_information_ids_objects",
                    "foreignField": "_id",
                    "as": "related_observable_informations"
                }
            },
            
            # Step 6: Join with measures if measure_id exists
            {
                "$lookup": {
                    "from": "measures",
                    "localField": "metadata.measure_id",
                    "foreignField": "_id", 
                    "as": "related_measures"
                }
            }
        ]
        
        db = self.mongo_api_service.client[dataset_id]
        entities = list(db[collection_name].aggregate(aggregation))

        # Convert ObjectIds to strings to avoid JSON serialization issues
        for entity in entities:
            self.mongo_api_service._fix_output_ids(entity)
        
        print(f"✅ Found {len(entities)} {self.entity_type} entities with nested data")
        return entities
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje TimeSeries z MongoDB na JSON-LD z zagnieżdżonymi elementami"""
        base_structure = self._create_basic_json_structure(entity_doc)

        properties = {}

        if "timestamp" in entity_doc and entity_doc["timestamp"]:
            properties["co:hasTimestamp"] = entity_doc["timestamp"]

        if "value" in entity_doc and entity_doc["value"]:
            properties["co:hasValue"] = entity_doc["value"]

        if "type" in entity_doc and entity_doc["type"]:
            properties["co:timeSeriesType"] = entity_doc["type"]

        if "metadata" in entity_doc and entity_doc["metadata"]:
            metadata = entity_doc["metadata"]
            
            if "source" in metadata and metadata["source"]:
                properties["co:timeSeriesSource"] = metadata["source"]
            
            # Dodaj properties z additional_properties
            if "additional_properties" in metadata and metadata["additional_properties"]:
                ts_properties = []
                for prop in metadata["additional_properties"]:
                    prop_obj = {
                        "@id": f"{prop['key']}{metadata['id']}",
                        "pc:hasKey": prop["key"],
                        "pc:hasValue": prop["value"]
                    }
                    ts_properties.append(prop_obj)
                properties["pc:hasProperty"] = ts_properties

        # Mapuj ObservableInformation z related_recordings
        if "related_recordings" in entity_doc and entity_doc["related_recordings"]:
            observable_infos = []
            
            for recording in entity_doc["related_recordings"]:
                if "observable_informations" in recording:
                    for obs_info in recording["observable_informations"]:
                        obs_info_obj = {
                            "@id": f"{obs_info['id']}"
                        }
                        
                        # Dodaj modality
                        if "modality_id" in obs_info and obs_info["modality_id"]:
                            obs_info_obj["co:hasModality"] = [{"@id": f"{obs_info['modality_id']}"}]
                        
                        # Dodaj life activity  
                        if "life_activity_id" in obs_info and obs_info["life_activity_id"]:
                            obs_info_obj["co:hasLifeActivity"] = [{"@id": f"{obs_info['life_activity_id']}"}]
                        
                        # Dodaj recording
                        recording_obj = {
                            "@id": f"{recording['_id']}"
                        }
                        
                        # Dodaj participations
                        if "related_participations" in entity_doc and entity_doc["related_participations"]:
                            participations = []
                            for participation in entity_doc["related_participations"]:
                                if participation["_id"] == recording["participation_id"]:
                                    participation_obj = {
                                        "@id": f"{participation['_id']}"
                                    }
                                    
                                    # Dodaj activity execution
                                    if "activity_execution_id" in participation:
                                        activity_exec_obj = {
                                            "@id": f"{participation['activity_execution_id']}"
                                        }
                                        participation_obj["co:hasActivityExecution"] = [activity_exec_obj]
                                    
                                    # Dodaj participant states
                                    if "related_participants" in entity_doc:
                                        for participant in entity_doc["related_participants"]:
                                            if "participant_states" in participant:
                                                for state in participant["participant_states"]:
                                                    if state["id"] == participation["participant_state_id"]:
                                                        state_obj = {
                                                            "@id": f"{state['id']}"
                                                        }
                                                        
                                                        # Dodaj participant
                                                        participant_obj = {
                                                            "@id": f"{participant['_id']}"
                                                        }
                                                        if "sex" in participant and participant["sex"]:
                                                            participant_obj["co:hasSex"] = [{"@id": f"co:sex{participant['sex']}"}]
                                                        
                                                        state_obj["co:hasParticipant"] = [participant_obj]
                                                        participation_obj["co:hasParticipantState"] = [state_obj]
                                    
                                    participations.append(participation_obj)
                            
                            recording_obj["co:hasParticipation"] = participations
                        
                        # Dodaj recording properties jeśli istnieją
                        if "additional_properties" in recording and recording["additional_properties"]:
                            recording_properties = []
                            for prop in recording["additional_properties"]:
                                prop_obj = {
                                    "@id": f":{prop['key']}{recording['_id']}",
                                    "pc:hasKey": prop["key"],
                                    "pc:hasValue": prop["value"]
                                }
                                recording_properties.append(prop_obj)
                            recording_obj["pc:hasProperty"] = recording_properties
                        
                        obs_info_obj["co:hasRecording"] = [recording_obj]
                        observable_infos.append(obs_info_obj)
            
            if observable_infos:
                properties["co:hasObservableInformation"] = observable_infos

        # Mapuj zagnieżdżone Measures - usuń puste measures
        if "related_measures" in entity_doc and entity_doc["related_measures"]:
            measures = []
            for measure in entity_doc["related_measures"]:
                measure_obj = {
                    "@id": f"{measure['_id']}"
                }
                
                if "measure_name_id" in measure and measure["measure_name_id"]:
                    measure_obj["co:hasMeasureName"] = [{"@id": measure["measure_name_id"]}]
                
                if "datatype" in measure and measure["datatype"]:
                    measure_obj["co:measureDatatype"] = measure["datatype"]
                
                if "range" in measure and measure["range"]:
                    measure_obj["co:measureRange"] = measure["range"]
                
                measures.append(measure_obj)
            
            if measures:
                properties["co:hasMeasure"] = measures
        
        # Mapuj measure_id z metadata jeśli related_measures jest puste
        elif "metadata" in entity_doc and "measure_id" in entity_doc["metadata"] and entity_doc["metadata"]["measure_id"]:
            properties["co:hasMeasure"] = [self._create_id_object(entity_doc["metadata"]["measure_id"])]

        base_structure.update(properties)
        return base_structure
