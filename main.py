from time import sleep
from grisera import activity_router
from grisera import activity_execution_router
from grisera import arrangement_router
from grisera import appearance_router
from grisera import channel_router
from grisera import experiment_router
from fastapi import FastAPI
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
from services.mongo_services import MongoServiceFactory
from grisera import time_series_router
from grisera import registered_data_router
from grisera import scenario_router
from grisera import measure_name_router
from setup import SetupNodes
import os

app = FastAPI(
    title="GRISERA API",
    description="Graph Representation Integrating Signals for Emotion Recognition and Analysis (GRISERA) "
    "framework provides a persistent model for storing integrated signals and methods for its "
    "creation.",
    version="0.1",
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

app.dependency_overrides[service.get_service_factory] = mongo_service.get_service_factory
@app.on_event("startup")
async def startup_event():
    startup = SetupNodes()
    sleep(2)
    if not os.path.exists("lock"):
        open("lock", "w").write("Busy")
        sleep(2)
        startup.set_activities()
        startup.set_channels()
        startup.set_arrangements()
        startup.set_modalities()
        startup.set_life_activities()
        startup.set_measure_names()
        os.remove("lock")


@app.get("/", tags=["root"])
async def root():
    """
    Return home page of api
    """
    response = {"title": "GRISERA API"}
    response.update({"links": get_links(app)})
    return response
