from typing import Union, List

import bson
import pymongo

from mongo_service.mongodb_api_config import mongo_api_address

client = pymongo.MongoClient(mongo_api_address)


class TimeSeriesRepository:
    """
    Repository for time series data access with optimized MongoDB aggregations.
    Handles complex queries and aggregations for time series filtering.
    """

    def __init__(self):
        self.client = client

    def find_by_activity_execution_and_participant(self,
                                                   dataset_id: Union[int, str],
                                                   activity_execution_id: str,
                                                   participant_id: str) -> List[str]:
        """
        Find time series IDs filtered by both activity execution and participant using MongoDB aggregation.
        
        Follows the relation chain:
        timeSeries -> recordings.observable_informations -> participations -> participants.participant_states
        
        Args:
            dataset_id (int | str): name of dataset
            activity_execution_id (str): Filter by activity execution id
            participant_id (str): Filter by participant id
            
        Returns:
            List of time series IDs that match both criteria
        """

        try:
            activity_execution_object_id = bson.ObjectId(activity_execution_id)
            participant_object_id = bson.ObjectId(participant_id)
        except bson.errors.InvalidId:
            return []

        db = self.client[dataset_id]
        aggregation = [
            # Step 0: Convert observable_information_ids strings to ObjectIds for proper lookup
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

            # Step 1: Join timeSeries with recordings through observable_informations
            {
                "$lookup": {
                    "from": "recordings",
                    "localField": "metadata.observable_information_ids_objects",
                    "foreignField": "observable_informations.id",
                    "as": "matched_recordings"
                }
            },
            {"$unwind": "$matched_recordings"},

            # Step 2: Join with participations through participation_id
            {
                "$lookup": {
                    "from": "participations",
                    "localField": "matched_recordings.participation_id",
                    "foreignField": "_id",
                    "as": "participations"
                }
            },
            {"$unwind": "$participations"},

            # Step 3: Join with participants through participant_state_id
            {
                "$lookup": {
                    "from": "participants",
                    "localField": "participations.participant_state_id",
                    "foreignField": "participant_states.id",
                    "as": "participants"
                }
            },
            {"$unwind": "$participants"},

            # Step 4: Filter by both criteria
            {
                "$match": {
                    "participations.activity_execution_id": activity_execution_object_id,
                    "participants._id": participant_object_id
                }
            },

            # Step 5: Group to get unique time series IDs
            {
                "$group": {
                    "_id": None,
                    "tsIds": {"$addToSet": "$metadata.id"}
                }
            },
            {"$project": {"_id": 0, "tsIds": 1}}
        ]

        aggregation_result = list(db["timeSeries"].aggregate(aggregation))

        if aggregation_result and "tsIds" in aggregation_result[0]:
            return [str(ts_id) for ts_id in aggregation_result[0]["tsIds"]]

        return []
