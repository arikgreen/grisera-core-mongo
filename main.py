from grisera import activity_router
from grisera import activity_execution_router
from grisera import arrangement_router
from grisera import appearance_router
from grisera import experiment_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from grisera import get_links
from grisera import life_activity_router
from grisera import measure_router
from grisera import modality_router
from grisera import observable_information_router
from grisera import participant_router
from grisera import participant_state_router
from grisera import participation_router
from grisera import personality_router
from grisera import recording_router
from grisera import registered_channel_router
from grisera import abstract_service as service
from services.mongo_service import service as mongo_service
from grisera import time_series_router
from grisera import registered_data_router
from grisera import scenario_router
from grisera import measure_name_router
from grisera import channel_router
from grisera import dataset_router

app = FastAPI(
    title="GRISERA API",
    description="Graph Representation Integrating Signals for Emotion Recognition and Analysis (GRISERA) "
                "framework provides a persistent model for storing integrated signals and methods for its "
                "creation.",
    version="0.1",
)

app.add_middleware(
    # to allow frontend and backend to be hosted on different domains (e.g., localhost:3000 for frontend and localhost:8000 for backend)
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["Authorization", "Content-Type"],  # Allow specific headers including Authorization ["Authorization", "Content-Type"]
)

app.include_router(activity_router)
app.include_router(activity_execution_router)
app.include_router(appearance_router)
app.include_router(arrangement_router)
app.include_router(channel_router)
app.include_router(experiment_router)
app.include_router(life_activity_router)
app.include_router(measure_router)
app.include_router(measure_name_router)
app.include_router(modality_router)
app.include_router(observable_information_router)
app.include_router(participant_router)
app.include_router(participant_state_router)
app.include_router(participation_router)
app.include_router(personality_router)
app.include_router(recording_router)
app.include_router(registered_channel_router)
app.include_router(registered_data_router)
app.include_router(scenario_router)
app.include_router(time_series_router)
app.include_router(dataset_router)

app.dependency_overrides[service.get_service_factory] = mongo_service.get_service_factory



@app.get("/", tags=["root"])
async def root():
    """
    Return home page of api
    """
    response = {"title": "GRISERA API"}
    response.update({"links": get_links(app)})
    return response
