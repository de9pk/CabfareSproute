import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from utils.location_helper import get_location_names, get_location_query
from jobs.fetch_fares import fetch_and_log
from utils.logging_config import setup_logging
from utils.config import HEADLESS

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Cab Fare Comparator API")

# Allow CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FareRequest(BaseModel):
    pickup: str
    destination: str
    platforms: List[str]
    mode: str = "real" # "demo" or "real"

class LocationResponse(BaseModel):
    locations: List[str]

@app.get("/api/locations", response_model=LocationResponse)
def get_locations():
    """Return preset locations."""
    locations = get_location_names()
    return {"locations": locations}

@app.post("/api/fares")
def fetch_fares(request: FareRequest):
    """Fetch fares for the given route."""
    pickup_query = get_location_query(request.pickup) if request.pickup in get_location_names() else request.pickup
    dest_query = get_location_query(request.destination) if request.destination in get_location_names() else request.destination
    
    if not pickup_query or not dest_query:
        raise HTTPException(status_code=400, detail="Invalid pickup or destination")
        
    try:
        results = fetch_and_log(
            pickup=pickup_query,
            destination=dest_query,
            selected=request.platforms,
            mode=request.mode,
            headless=HEADLESS
        )
        return {"results": results}
    except Exception as e:
        logger.error(f"Error fetching fares: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
