import os
import httpx
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

FLIGHT_SERVICE_URL = os.getenv("FLIGHT_SERVICE_URL", "http://127.0.0.1:8003/search-flights")
HOTEL_SERVICE_URL = os.getenv("HOTEL_SERVICE_URL", "http://127.0.0.1:8004/search-hotels")

@tool
async def search_flights(origin: str, destination: str, depart_date: str, adults: int = 1) -> dict:
    """Search for available flights using the Duffel Flight Microservice."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                FLIGHT_SERVICE_URL,
                params={
                    "origin": origin,
                    "destination": destination,
                    "depart_date": depart_date
                },
                timeout=10.0
            )
            if response.status_code == 200:
                return response.json()
            return {"error": f"HTTP {response.status_code}", "flights": []}
        except Exception as e:
            return {"error": str(e), "flights": []}

@tool
async def search_hotels(destination: str, checkin_date: str, checkout_date: str, adults: int = 1) -> dict:
    """Search for available accommodations using the Duffel Hotel Microservice."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                HOTEL_SERVICE_URL,
                params={
                    "destination": destination,
                    "check_in": checkin_date,
                    "check_out": checkout_date
                },
                timeout=10.0
            )
            if response.status_code == 200:
                return response.json()
            return {"error": f"HTTP {response.status_code}", "hotels": []}
        except Exception as e:
            return {"error": str(e), "hotels": []}