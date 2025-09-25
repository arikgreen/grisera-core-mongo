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

        if "recording_id" in entity_doc and entity_doc["recording_id"]:
            base_structure["co:hasRecording"] = [self._create_id_object(entity_doc["recording_id"])]

        if "modality_id" in entity_doc and entity_doc["modality_id"]:
            base_structure["co:hasModality"] = [self._create_id_object(entity_doc["modality_id"])]

        if "life_activity_id" in entity_doc and entity_doc["life_activity_id"]:
            base_structure["co:hasLifeActivity"] = [self._create_id_object(entity_doc["life_activity_id"])]

        return base_structure
