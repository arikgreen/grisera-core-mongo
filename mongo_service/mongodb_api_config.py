# parameters of mongo_api used in API
import os

mongo_api_host = os.environ.get("MONGO_API_HOST") or "localhost"
mongo_api_port = os.environ.get("MONGO_API_PORT") or "27017"
mongo_api_address = f"mongodb://{mongo_api_host}:{mongo_api_port}"

mongo_database_name = os.environ.get("MONGO_DATABASE") or "road"
