"""
Recording JSON-LD Helper
"""
import json
from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class RecordingJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji Recording -> co:Recording."""
    
    def _get_entity_type(self) -> str:
        return "Recording"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:Recording"
    
    def get_collection_enum(self) -> Collections:
        return Collections.RECORDING
    
    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera Recording dla dataset_id z zagnieżdżonymi elementami używając agregacji MongoDB.
        Pobiera powiązane Participations, Participants, RegisteredChannels i ObservableInformations.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        
        collection_name = self.get_collection_enum().value
        
        aggregation = [
            # Step 1: Join with participations
            {
                "$lookup": {
                    "from": "participations",
                    "localField": "participation_id",
                    "foreignField": "_id",
                    "as": "related_participations"
                }
            },
            
            # Step 2: Join with participants through participation participant_state_id
            {
                "$lookup": {
                    "from": "participants",
                    "localField": "related_participations.participant_state_id",
                    "foreignField": "participant_states.id",
                    "as": "related_participants"
                }
            },
            
            # Step 3: Join with registered_channels
            {
                "$lookup": {
                    "from": "registered_channels",
                    "localField": "registered_channel_id",
                    "foreignField": "_id",
                    "as": "related_registered_channels"
                }
            },
            
            # Step 4: Join with channels through registered_channel
            {
                "$lookup": {
                    "from": "channels",
                    "localField": "related_registered_channels.channel_id",
                    "foreignField": "_id",
                    "as": "related_channels"
                }
            },
            
            # Step 5: Join with registered_data through registered_channel registered_data_id
            {
                "$lookup": {
                    "from": "registered_data",
                    "localField": "related_registered_channels.registered_data_id",
                    "foreignField": "_id",
                    "as": "related_registered_data"
                }
            },
            
            # Step 6: Add field for activity_execution_ids from participations
            {
                "$addFields": {
                    "activity_execution_ids": "$related_participations.activity_execution_id"
                }
            },
            
            # Step 7: Convert activity_execution_ids to ObjectIds for proper lookup
            {
                "$addFields": {
                    "activity_execution_ids_objects": {
                        "$map": {
                            "input": "$activity_execution_ids",
                            "as": "ae_id",
                            "in": {"$toObjectId": "$$ae_id"}
                        }
                    }
                }
            },
            
            # Step 8: Join with activities collection and find matching activity_executions
            {
                "$lookup": {
                    "from": "activities",
                    "localField": "activity_execution_ids_objects",
                    "foreignField": "activity_executions.id",
                    "as": "related_activities_with_executions"
                }
            },
            
            # Step 9: Extract matching activity_executions and activities
            {
                "$addFields": {
                    "related_activity_executions": {
                        "$reduce": {
                            "input": "$related_activities_with_executions",
                            "initialValue": [],
                            "in": {
                                "$concatArrays": [
                                    "$$value",
                                    {
                                        "$filter": {
                                            "input": "$$this.activity_executions",
                                            "cond": {"$in": ["$$this.id", "$activity_execution_ids_objects"]}
                                        }
                                    }
                                ]
                            }
                        }
                    },
                    "related_activities": "$related_activities_with_executions"
                }
            },
            
            # Step 10: Join with appearances through participant_states appearance_ids
            {
                "$lookup": {
                    "from": "appearances",
                    "localField": "related_participants.participant_states.appearance_ids",
                    "foreignField": "_id",
                    "as": "related_appearances"
                }
            }
        ]
        
        db = self.mongo_api_service.client[dataset_id]
        entities = list(db[collection_name].aggregate(aggregation))

        # Convert ObjectIds to strings to avoid JSON serialization issues
        for entity in entities:
            self.mongo_api_service._fix_output_ids(entity)

        # nie usuwaj tego printa - bardzo pomaga w debugowaniu
        # print(json.dumps(entities, indent=2, default=str))
        # raise Exception("Debug stop")

        print(f"✅ Found {len(entities)} {self.entity_type} entities with nested data")
        return entities
    
    def map_to_json(self, entity_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Mapuje Recording z MongoDB na JSON-LD z zagnieżdżonymi elementami"""
        base_structure = self._create_basic_json_structure(entity_doc)
        
        properties = {}
        
        # Mapuj zagnieżdżone RegisteredChannels
        if "related_registered_channels" in entity_doc and entity_doc["related_registered_channels"]:
            registered_channels = []
            for reg_channel in entity_doc["related_registered_channels"]:
                reg_channel_obj = {
                    "@id": f"{reg_channel['_id']}"
                }
                
                # Dodaj zagnieżdżone RegisteredData - sprawdź czy registered_data należy do tego kanału
                if reg_channel.get("registered_data_id"):
                    reg_data_obj = {
                        "@id": f"{reg_channel['registered_data_id']}"
                    }
                    reg_channel_obj["co:hasRegisteredData"] = [reg_data_obj]
                
                # Dodaj zagnieżdżone Channels
                if "related_channels" in entity_doc and entity_doc["related_channels"]:
                    for channel in entity_doc["related_channels"]:
                        if channel["_id"] == reg_channel.get("channel_id"):
                            # Mapuj typ kanału na odpowiedni ID
                            channel_type = channel.get("type", "Unknown")
                            reg_channel_obj["co:hasChannel"] = [{"@id": f"co:channel{channel_type}"}]
                
                registered_channels.append(reg_channel_obj)
            
            if registered_channels:
                properties["co:hasRegisteredChannel"] = registered_channels
        
        # Mapuj zagnieżdżone Participations
        if "related_participations" in entity_doc and entity_doc["related_participations"]:
            participations = []
            for participation in entity_doc["related_participations"]:
                if participation["_id"] == entity_doc.get("participation_id"):
                    participation_obj = {
                        "@id": f"{participation['_id']}"
                    }
                    
                    # Dodaj ActivityExecution (zawsze gdy participation ma activity_execution_id)
                    if "activity_execution_id" in participation and participation["activity_execution_id"]:
                        activity_exec_obj = {
                            "@id": f"{participation['activity_execution_id']}"
                        }
                        
                        # Znajdź powiązane activity_id i dodaj co:hasActivity
                        activity_id = None
                        if "related_activity_executions" in entity_doc and entity_doc["related_activity_executions"]:
                            for activity_exec in entity_doc["related_activity_executions"]:
                                if activity_exec.get("id") == participation["activity_execution_id"]:
                                    activity_id = activity_exec.get("activity_id")
                                    break
                        
                        # Dodaj co:hasActivity jeśli znaleziono activity_id lub activity w related_activities
                        if activity_id:
                            activity_obj = {"@id": f"{activity_id}"}
                            activity_exec_obj["co:hasActivity"] = [activity_obj]
                        elif "related_activities" in entity_doc and entity_doc["related_activities"]:
                            # Fallback - użyj pierwszego dostępnego activity
                            for activity in entity_doc["related_activities"]:
                                activity_obj = {"@id": f"{activity['_id']}"}
                                activity_exec_obj["co:hasActivity"] = [activity_obj]
                                break
                        
                        participation_obj["co:hasActivityExecution"] = [activity_exec_obj]
                    
                    # Dodaj zagnieżdżone ParticipantStates
                    if "related_participants" in entity_doc and entity_doc["related_participants"]:
                        for participant in entity_doc["related_participants"]:
                            if "participant_states" in participant:
                                for state in participant["participant_states"]:
                                    if state["id"] == participation.get("participant_state_id"):
                                        state_obj = {
                                            "@id": f"{state['id']}"
                                        }
                                        
                                        # Dodaj zagnieżdżone Appearances
                                        if "related_appearances" in entity_doc and entity_doc["related_appearances"]:
                                            appearances = []
                                            if "appearance_ids" in state and state["appearance_ids"]:
                                                for appearance_id in state["appearance_ids"]:
                                                    for appearance in entity_doc["related_appearances"]:
                                                        if appearance["_id"] == appearance_id:
                                                            appearance_obj = {
                                                                "@id": f"{appearance['_id']}"
                                                            }
                                                            # Dodaj appearance properties
                                                            if "moustache_value" in appearance:
                                                                appearance_obj["appearanceOcclusion:hasMoustacheValue"] = [{"@id": f"appearanceOcclusion:appearance{appearance['moustache_value']}"}]
                                                            if "beard_value" in appearance:
                                                                appearance_obj["appearanceOcclusion:hasBeardValue"] = [{"@id": f"appearanceOcclusion:appearance{appearance['beard_value']}"}]
                                                            if "glasses" in appearance:
                                                                appearance_obj["appearanceOcclusion:hasGlasses"] = str(appearance["glasses"]).lower()
                                                            appearances.append(appearance_obj)
                                            
                                            if appearances:
                                                state_obj["co:hasApperance"] = appearances
                                        
                                        # Dodaj zagnieżdżone Participant
                                        participant_obj = {
                                            "@id": f"{participant['_id']}"
                                        }
                                        if "sex" in participant and participant["sex"]:
                                            participant_obj["co:hasSex"] = [{"@id": f"co:sex{participant['sex']}"}]
                                        
                                        state_obj["co:hasParticipant"] = [participant_obj]
                                        participation_obj["co:hasParticipantState"] = [state_obj]
                    
                    participations.append(participation_obj)
            
            if participations:
                properties["co:hasParticipation"] = participations
        
        # Mapuj properties z additional_properties (recording level)
        recording_properties = []
        if "additional_properties" in entity_doc and entity_doc["additional_properties"]:
            for prop in entity_doc["additional_properties"]:
                prop_obj = {
                    "@id": f"{prop['key']}{entity_doc['_id']}",
                    "pc:hasKey": prop["key"],
                    "pc:hasValue": prop["value"]
                }
                recording_properties.append(prop_obj)
        
        # Dodaj properties z related_registered_data
        if "related_registered_data" in entity_doc and entity_doc["related_registered_data"]:
            for reg_data in entity_doc["related_registered_data"]:
                if "additional_properties" in reg_data and reg_data["additional_properties"]:
                    for prop in reg_data["additional_properties"]:
                        prop_obj = {
                            "@id": f"{prop['key']}{entity_doc['_id']}",
                            "pc:hasKey": prop["key"],
                            "pc:hasValue": prop["value"]
                        }
                        recording_properties.append(prop_obj)
        
        if recording_properties:
            properties["pc:hasProperty"] = recording_properties

        base_structure.update(properties)
        return base_structure
