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

        if 'participation_id' in entity_doc and entity_doc['participation_id']:
            base_structure["co:hasParticipation"] = [{"@id": f"{entity_doc['participation_id']}"}]

        if 'registered_channel_id' in entity_doc and entity_doc['registered_channel_id']:
            base_structure["co:hasRegisteredChannel"] = [{"@id": f"{entity_doc['registered_channel_id']}"}]

        return base_structure
