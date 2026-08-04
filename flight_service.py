import os
from typing import List
from fastapi import FastAPI, Query
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx
import uvicorn


load_dotenv()
DUFFEL_TOKEN = os.getenv("DUFFEL_ACCESS_TOKEN", "")

app = FastAPI(title="Duffel Flight Microservice")

class FlightOffer(BaseModel):
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    price: float
    currency: str

class FlightSearchResponse(BaseModel):
    origin: str
    destination: str
    depart_date: str
    flights: List[FlightOffer]
    source: str

CACHE: dict = {}

FALLBACK_FLIGHTS = [
    {
        "airline": "IndiGo (Fallback)",
        "flight_number": "6E-204",
        "origin": "BOM",
        "destination": "GOI",
        "departure_time": "2026-08-10T08:30:00",
        "price": 5400.0,
        "currency": "INR"
    },
    {
        "airline": "Air India (Fallback)",
        "flight_number": "AI-802",
        "origin": "BOM",
        "destination": "GOI",
        "departure_time": "2026-08-10T14:15:00",
        "price": 6200.0,
        "currency": "INR"
    }
]

@app.get("/")
async def root():
    return {"status": "Online", "service": "Flight Microservice"}

@app.get("/search-flights", response_model=FlightSearchResponse)
async def search_flights(
    origin: str = Query("BOM", description="3-letter IATA code"),
    destination: str = Query("GOI", description="3-letter IATA code"),
    depart_date: str = Query("2026-08-10", description="YYYY-MM-DD format")
):
    origin_code = origin.strip().upper()
    dest_code = destination.strip().upper()
    cache_key = f"{origin_code}_{dest_code}_{depart_date}"

 
    if cache_key in CACHE:
        return FlightSearchResponse(
            origin=origin_code,
            destination=dest_code,
            depart_date=depart_date,
            flights=CACHE[cache_key],
            source="Local Cache (0ms Latency)"
        )

    
    if DUFFEL_TOKEN and not DUFFEL_TOKEN.startswith("duffel_test_YOUR"):
        try:
            headers = {
                "Authorization": f"Bearer {DUFFEL_TOKEN}",
                "Duffel-Version": "v2",
                "Content-Type": "application/json"
            }
            payload = {
                "data": {
                    "slices": [
                        {
                            "origin": origin_code,
                            "destination": dest_code,
                            "departure_date": depart_date
                        }
                    ],
                    "passengers": [{"type": "adult"}, {"type": "adult"}],
                    "cabin_class": "economy"
                }
            }

            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.duffel.com/air/offer_requests?return_offers=true",
                    headers=headers,
                    json=payload,
                    timeout=12.0
                )

                if res.status_code in [200, 201]:
                    offers = res.json().get("data", {}).get("offers", [])
                    parsed_flights = []

                    for offer in offers[:5]:
                        slices = offer.get("slices", [])
                        if not slices:
                            continue
                        segments = slices[0].get("segments", [])
                        if not segments:
                            continue
                        
                        segment = segments[0]
                        owner = offer.get("owner", {})
                        
                        parsed_flights.append(
                            FlightOffer(
                                airline=owner.get("name", "Partner Airline"),
                                flight_number=str(segment.get("marketing_carrier_flight_number", "FL-101")),
                                origin=origin_code,
                                destination=dest_code,
                                departure_time=str(segment.get("departing_at", "10:00")),
                                price=float(offer.get("total_amount", 5000.0)),
                                currency=str(offer.get("total_currency", "INR"))
                            )
                        )

                    if parsed_flights:
                        CACHE[cache_key] = [f.model_dump() for f in parsed_flights]
                        return FlightSearchResponse(
                            origin=origin_code,
                            destination=dest_code,
                            depart_date=depart_date,
                            flights=parsed_flights,
                            source="Duffel Live API (Test Sandbox)"
                        )
                else:
                    print(f"[DUFFEL API RESPONSE ERROR]: {res.status_code} - {res.text}")

        except Exception as e:
            print(f"[DUFFEL FLIGHT API ERROR]: {e}")

   
    fallback_response = [
        FlightOffer(
            airline=item["airline"],
            flight_number=item["flight_number"],
            origin=origin_code,
            destination=dest_code,
            departure_time=item["departure_time"],
            price=item["price"],
            currency=item["currency"]
        ) for item in FALLBACK_FLIGHTS
    ]

    return FlightSearchResponse(
        origin=origin_code,
        destination=dest_code,
        depart_date=depart_date,
        flights=fallback_response,
        source="Resilient Safety Fallback"
    )

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8003)