import os
from typing import List
from fastapi import FastAPI, Query
from pydantic import BaseModel
from dotenv import load_dotenv
import httpx
import uvicorn
from datetime import datetime

load_dotenv(override=True)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "").strip()
RAPIDAPI_HOST = "booking-com15.p.rapidapi.com"

app = FastAPI(title="Fully Dynamic RapidAPI Hotel Microservice")

class HotelOffer(BaseModel):
    hotel_name: str
    location: str
    check_in: str
    check_out: str
    price_per_night: float
    currency: str

class HotelSearchResponse(BaseModel):
    destination: str
    hotels: List[HotelOffer]
    source: str

CACHE: dict = {}

@app.get("/")
async def root():
    return {"status": "Online", "service": "Dynamic Hotel Microservice"}

async def get_destination_id(client: httpx.AsyncClient, query: str, headers: dict) -> str:
    """Dynamically queries RapidAPI and prioritizes actual cities over partial matches like Delray Beach."""
    search_url = f"https://{RAPIDAPI_HOST}/api/v1/hotels/searchDestination"
    params = {"query": query}
    
    try:
        res = await client.get(search_url, headers=headers, params=params, timeout=10.0)
        if res.status_code == 200:
            data = res.json().get("data", [])
            if data and isinstance(data, list):
                for item in data:
                    if item.get("dest_type") == "city" or item.get("search_type") == "city":
                        name = item.get("name", "").lower()
                        if query.lower() == "del" and "new delhi" in name:
                            dest_id = item.get("dest_id") or item.get("id")
                            if dest_id:
                                print(f"[SMART MATCH FOUND]: {dest_id} for '{item.get('name')}'")
                                return str(dest_id)
                        elif query.lower() != "del":
                            dest_id = item.get("dest_id") or item.get("id")
                            if dest_id:
                                return str(dest_id)
                
               
                for item in data:
                    if item.get("dest_type") == "city" or item.get("search_type") == "city":
                        dest_id = item.get("dest_id") or item.get("id")
                        if dest_id:
                            return str(dest_id)
                            
               
                first_match = data[0]
                dest_id = first_match.get("dest_id") or first_match.get("id")
                if dest_id:
                    return str(dest_id)
    except Exception as e:
        print(f"[DESTINATION LOOKUP EXCEPTION]: {e}")
        
    return ""

@app.get("/search-hotels", response_model=HotelSearchResponse)
async def search_hotels(
    destination: str = Query(..., description="Type any city name or code like DEL, Mumbai, Goa, Paris"),
    check_in: str = Query("2026-08-10", description="YYYY-MM-DD"),
    check_out: str = Query("2026-08-15", description="YYYY-MM-DD")

    
):
    dest_query = destination.strip()
    cache_key = f"{dest_query.lower()}_{check_in}_{check_out}"

    
    if cache_key in CACHE:
        return HotelSearchResponse(
            destination=dest_query.upper(),
            hotels=CACHE[cache_key],
            source="Local Cache (0ms Latency)"
        )

    if not RAPIDAPI_KEY:
        return HotelSearchResponse(
            destination=dest_query.upper(),
            hotels=[],
            source="Error: RAPIDAPI_KEY is missing in .env"
        )

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }


    try:
        d1 = datetime.strptime(check_in, "%Y-%m-%d")
        d2 = datetime.strptime(check_out, "%Y-%m-%d")
        num_nights = (d2 - d1).days
        if num_nights <= 0:
            num_nights = 1 
    except Exception:
        num_nights = 5

    async with httpx.AsyncClient() as client:
        
        dest_id = await get_destination_id(client, dest_query, headers)
        
        if not dest_id:
            return HotelSearchResponse(
                destination=dest_query.upper(),
                hotels=[],
                source=f"Error: Could not dynamically resolve destination ID for '{dest_query}'."
            )

      
        params = {
            "dest_id": dest_id,
            "search_type": "CITY",
            "arrival_date": check_in,
            "departure_date": check_out,
            "adults": "2",
            "room_qty": "1",
            "page_number": "1",
            "units": "metric",
            "temperature_unit": "c",
            "languagecode": "en-us",
            "currency_code": "INR"
        }

        try:
            res = await client.get(
                f"https://{RAPIDAPI_HOST}/api/v1/hotels/searchHotels",
                headers=headers,
                params=params,
                timeout=15.0
            )

            if res.status_code == 200:
                data = res.json().get("data", {})
                results = data.get("hotels", []) or data.get("result", [])
                parsed_hotels = []

                for item in results[:5]:
                    hotel_info = item.get("property", item)
                    name = hotel_info.get("name", item.get("hotel_name", "Real Hotel"))

                    price_info = item.get("property", {}).get("priceBreakdown", {}) or item.get("priceBreakdown", {})
                    gross = price_info.get("grossPrice", {})
                    
                    if isinstance(gross, dict):
                        total_price = float(gross.get("value", 15000.0))
                    else:
                        total_price = float(gross) if gross else 15000.0

                    price_per_night = round(total_price / num_nights, 2) if total_price > 0 else 4500.0

                    parsed_hotels.append(
                        HotelOffer(
                            hotel_name=name,
                            location=dest_query.upper(),
                            check_in=check_in,
                            check_out=check_out,
                            price_per_night=price_per_night,
                            currency="INR"
                        )
                    )

                if parsed_hotels:
                    CACHE[cache_key] = [h.model_dump() for h in parsed_hotels]
                    return HotelSearchResponse(
                        destination=dest_query.upper(),
                        hotels=parsed_hotels,
                        source="Fully Dynamic RapidAPI Live Data"
                    )
            else:
                print(f"[RAPIDAPI HOTEL ERROR {res.status_code}]: {res.text}")

        except Exception as e:
            print(f"[RAPIDAPI HOTEL EXCEPTION]: {e}")

    return HotelSearchResponse(
        destination=dest_query.upper(),
        hotels=[],
        source="No hotels found or live query failed."
    )

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8004)