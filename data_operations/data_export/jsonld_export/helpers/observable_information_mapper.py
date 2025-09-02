"""
ObservableInformation JSON-LD Helper
"""

from typing import Dict, Any, List
from .base_mapper import BaseJsonLdHelper
from mongo_service.collection_mapping import Collections


class ObservableInformationJsonLdHelper(BaseJsonLdHelper):
    """Helper dla encji ObservableInformation -> co:ObservableInformation."""
    
    def _get_entity_type(self) -> str:
        return "ObservableInformation"
    
    def get_jsonld_collection_key(self) -> str:
        return "co:ObservableInformation"

    def get_collection_enum(self) -> Collections:
        # ObservableInformation są zagnieżdżone w kolekcji RECORDING
        return Collections.RECORDING

    def fetch_entities(self, dataset_id: str) -> List[Dict[str, Any]]:
        """
        Pobiera ObservableInformation dla dataset_id z zagnieżdżonymi elementami używając agregacji MongoDB.
        Pobiera powiązane Recordings, Participations, Participants, TimeSeries, Modalities, LifeActivities.
        """
        print(f"🔍 Fetching {self.entity_type} from collection: {self.get_collection_enum().value}")
        
        collection_name = self.get_collection_enum().value
        
        aggregation = [
            # Step 1: Unwind observable_informations to work with individual items
            {"$unwind": "$observable_informations"},
            
            # Step 2: Join with participations
            {
                "$lookup": {
                    "from": "participations",
                    "localField": "participation_id",
                    "foreignField": "_id",
                    "as": "related_participations"
                }
            },
            
            # Step 3: Join with participants through participation participant_state_id
            {
                "$lookup": {
                    "from": "participants",
                    "localField": "related_participations.participant_state_id",
                    "foreignField": "participant_states.id",
                    "as": "related_participants"
                }
            },
            
            # Step 4: Join with timeSeries through observable_information_id
            {
                "$lookup": {
                    "from": "timeSeries",
                    "localField": "observable_informations.id",
                    "foreignField": "metadata.observable_information_id",
                    "as": "related_time_series"
                }
            },
            
            # Step 5: Join with modalities
            {
                "$lookup": {
                    "from": "modalities",
                    "localField": "observable_informations.modality_id",
                    "foreignField": "_id",
                    "as": "related_modalities"
                }
            },
            
            # Step 6: Join with life_activities
            {
                "$lookup": {
                    "from": "life_activities",
                    "localField": "observable_informations.life_activity_id",
                    "foreignField": "_id",
                    "as": "related_life_activities"
                }
            },
            
            # Step 7: Join with registered_channels
            {
                "$lookup": {
                    "from": "registered_channels",
                    "localField": "registered_channel_id",
                    "foreignField": "_id",
                    "as": "related_registered_channels"
                }
            },
            
            # Step 8: Join with channels through registered_channel
            {
                "$lookup": {
                    "from": "channels",
                    "localField": "related_registered_channels.channel_id",
                    "foreignField": "_id",
                    "as": "related_channels"
                }
            },
            
            # Step 9: Join with registered_data through registered_channel
            {
                "$lookup": {
                    "from": "registered_data",
                    "localField": "related_registered_channels.registered_data_id",
                    "foreignField": "_id",
                    "as": "related_registered_data"
                }
            },
            
            # Step 10: Add activity_execution_ids from participations
            {
                "$addFields": {
                    "activity_execution_ids": "$related_participations.activity_execution_id"
                }
            },
            
            # Step 11: Join with activities to get activity_executions
            {
                "$lookup": {
                    "from": "activities",
                    "localField": "activity_execution_ids",
                    "foreignField": "activity_executions.id",
                    "as": "related_activities_with_executions"
                }
            },
            
            # Step 12: Extract matching activity_executions and activities
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
                                            "cond": {"$in": ["$$this.id", "$activity_execution_ids"]}
                                        }
                                    }
                                ]
                            }
                        }
                    },
                    "related_activities": "$related_activities_with_executions"
                }
            },
            
            # Step 13: Project the observable_information as the main document
            {
                "$replaceRoot": {
                    "newRoot": {
                        "$mergeObjects": [
                            "$observable_informations",
                            {
                                "_parent_recording": {
                                    "_id": "$_id",
                                    "participation_id": "$participation_id",
                                    "registered_channel_id": "$registered_channel_id"
                                },
                                "related_participations": "$related_participations",
                                "related_participants": "$related_participants",
                                "related_time_series": "$related_time_series",
                                "related_modalities": "$related_modalities",
                                "related_life_activities": "$related_life_activities",
                                "related_activity_executions": "$related_activity_executions",
                                "related_activities": "$related_activities",
                                "related_registered_channels": "$related_registered_channels",
                                "related_channels": "$related_channels",
                                "related_registered_data": "$related_registered_data"
                            }
                        ]
                    }
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
        """Mapuje ObservableInformation z MongoDB na JSON-LD z zagnieżdżonymi elementami"""
        base_structure = self._create_basic_json_structure(entity_doc)
        
        properties = {}
        
        # Mapuj zagnieżdżone Recording
        if "_parent_recording" in entity_doc and entity_doc["_parent_recording"]:
            parent_recording = entity_doc["_parent_recording"]
            recording_obj = {
                "@id": f"{parent_recording['_id']}"
            }
            
            # Dodaj zagnieżdżone Participations
            if "related_participations" in entity_doc and entity_doc["related_participations"]:
                participations = []
                for participation in entity_doc["related_participations"]:
                    if participation["_id"] == parent_recording.get("participation_id"):
                        participation_obj = {
                            "@id": f"{participation['_id']}"
                        }
                        
                        # Dodaj ActivityExecution
                        if "activity_execution_id" in participation and participation["activity_execution_id"]:
                            activity_exec_obj = {
                                "@id": f"{participation['activity_execution_id']}"
                            }
                            
                            # Znajdź powiązane activity_id i dodaj co:hasActivity
                            if "related_activity_executions" in entity_doc:
                                for activity_exec in entity_doc["related_activity_executions"]:
                                    if activity_exec.get("id") == participation["activity_execution_id"]:
                                        activity_id = activity_exec.get("activity_id")
                                        if activity_id:
                                            activity_obj = {"@id": f"{activity_id}"}
                                            activity_exec_obj["co:hasActivity"] = [activity_obj]
                                        break
                            
                            participation_obj["co:hasActivityExecution"] = [activity_exec_obj]
                        
                        # Dodaj ParticipantState
                        if "related_participants" in entity_doc:
                            for participant in entity_doc["related_participants"]:
                                if "participant_states" in participant:
                                    for state in participant["participant_states"]:
                                        if state["id"] == participation.get("participant_state_id"):
                                            state_obj = {
                                                "@id": f"{state['id']}"
                                            }
                                            
                                            # Dodaj Participant
                                            participant_obj = {
                                                "@id": f"{participant['_id']}"
                                            }
                                            if "sex" in participant and participant["sex"]:
                                                participant_obj["co:hasSex"] = [{"@id": f"co:sex{participant['sex']}"}]
                                            
                                            state_obj["co:hasParticipant"] = [participant_obj]
                                            participation_obj["co:hasParticipantState"] = [state_obj]
                        
                        participations.append(participation_obj)
                
                if participations:
                    recording_obj["co:hasParticipation"] = participations
            
            # Dodaj zagnieżdżone RegisteredChannels
            if "related_registered_channels" in entity_doc and entity_doc["related_registered_channels"]:
                registered_channels = []
                for reg_channel in entity_doc["related_registered_channels"]:
                    if reg_channel["_id"] == parent_recording.get("registered_channel_id"):
                        reg_channel_obj = {
                            "@id": f"{reg_channel['_id']}"
                        }
                        
                        # Dodaj zagnieżdżone RegisteredData
                        if reg_channel.get("registered_data_id"):
                            reg_data_obj = {
                                "@id": f"{reg_channel['registered_data_id']}"
                            }
                            reg_channel_obj["co:hasRegisteredData"] = [reg_data_obj]
                        
                        # Dodaj zagnieżdżone Channels
                        if "related_channels" in entity_doc and entity_doc["related_channels"]:
                            for channel in entity_doc["related_channels"]:
                                if channel["_id"] == reg_channel.get("channel_id"):
                                    channel_type = channel.get("type", "Unknown")
                                    reg_channel_obj["co:hasChannel"] = [{"@id": f"co:channel{channel_type}"}]
                        
                        registered_channels.append(reg_channel_obj)
                
                if registered_channels:
                    recording_obj["co:hasRegisteredChannel"] = registered_channels
            
            properties["co:hasRecording"] = [recording_obj]

        # Mapuj Modality
        if "modality_id" in entity_doc and entity_doc["modality_id"]:
            properties["co:hasModality"] = [{"@id": entity_doc["modality_id"]}]

        # Mapuj LifeActivity
        if "life_activity_id" in entity_doc and entity_doc["life_activity_id"]:
            properties["co:hasLifeActivity"] = [{"@id": entity_doc["life_activity_id"]}]
        
        base_structure.update(properties)
        return base_structure
