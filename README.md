# GRISERA APP

## GRISERA framework
Graph Representation Integrating Signals for Emotion Recognition and Analysis (GRISERA) framework provides a persistent model for storing integrated signals and methods for its creation.

### Setting up the development environment 
### Components
1. virtualenv (build in Python3)
1. FastAPI framework
1. Uvicorn ASGI server

### Prerequisites
1. python3-venv 
1. python3-dev

### Setup steps
1. `$ python3 -m venv venv`
1. `$ source venv/bin/activate`
1. `(venv) $ pip install -r requirements.txt`

### Start Uvicorn server 
`(venv) $ uvicorn main:app --reload`
