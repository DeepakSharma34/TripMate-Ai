import os
from typing import Dict, List, TypedDict
from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
import uvicorn

from mcp_tools import search_flights, search_hotels

load_dotenv()

FLIGHT_SERVICE_URL = os.getenv("FLIGHT_SERVICE_URL", "http://localhost:8000")
HOTEL_SERVICE_URL = os.getenv("HOTEL_SERVICE_URL", "http://localhost:8000")

api_key =  os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("API Key not found! Please set GOOGLE_API_KEY in your .env file.")

app = FastAPI(title="TripMate AI Travel Concierge")

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    api_key=api_key,
    temperature=0.7,
)

class TripRequest(BaseModel):
    origin: str = Field(default="BOM", description="Flight origin airport code (e.g. BOM)")
    destination: str = Field(default="GOI", description="Flight destination airport code (e.g. GOI)")
    departure_date: str = Field(default="2026-08-10", description="YYYY-MM-DD")
    return_date: str = Field(default="2026-08-15", description="YYYY-MM-DD")
    passengers: int = Field(default=2, description="Number of travelers")
    budget_inr: float = Field(default=30000, description="Total budget in INR")
    duration_days: int = Field(default=5, description="Number of days for the trip")

class PlanState(TypedDict):
    request: Dict
    flight_data: Dict
    hotel_data: Dict
    executed_nodes: List[str]
    final_itinerary: str

def extract_clean_text(response) -> str:
    content = getattr(response, "content", response)

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if "text" in item and isinstance(item["text"], str):
                    text_parts.append(item["text"])
            elif hasattr(item, "text"):
                text_parts.append(str(getattr(item, "text")))
            elif isinstance(item, str):
                text_parts.append(item)
            else:
                text_parts.append(str(item))
        return "\n".join(text_parts).strip()

    if isinstance(content, dict):
        return str(content.get("text", content)).strip()

    return str(content).strip()

async def fetch_flights_node(state: PlanState) -> Dict:
    req = state.get("request", {})
    flight_info = await search_flights.ainvoke({
        "origin": req.get("origin", "BOM"),
        "destination": req.get("destination", "GOI"),
        "depart_date": req.get("departure_date", "2026-08-10"),
        "adults": req.get("passengers", 2)
    })
    executed = state.get("executed_nodes", []) + ["fetch_flights"]
    return {"flight_data": flight_info, "executed_nodes": executed}

async def fetch_hotels_node(state: PlanState) -> Dict:
    req = state.get("request", {})
    hotel_info = await search_hotels.ainvoke({
        "destination": req.get("destination", "GOI"),
        "checkin_date": req.get("departure_date", "2026-08-10"),
        "checkout_date": req.get("return_date", "2026-08-15"),
        "adults": req.get("passengers", 2)
    })
    executed = state.get("executed_nodes", []) + ["fetch_hotels"]
    return {"hotel_data": hotel_info, "executed_nodes": executed}

async def synthesize_itinerary_node(state: PlanState) -> Dict:
    req = state.get("request", {})
    prompt = f"""
    You are TripMate AI Travel Concierge. Synthesize a detailed, budget-friendly {req.get('duration_days', 5)}-day trip to {req.get('destination', 'GOI')} for {req.get('passengers', 2)} adults with a total budget of ₹{req.get('budget_inr', 30000)} based on these options:
    
    Flights: {state.get('flight_data')}
    Hotels: {state.get('hotel_data')}
    
    Provide cost breakdowns, daily activities, and budget tips using clear markdown tables and bullet points.
    """

    response = await llm.ainvoke(prompt)
    clean_itinerary_text = extract_clean_text(response)
    executed = state.get("executed_nodes", []) + ["synthesize_itinerary"]

    return {
        "final_itinerary": clean_itinerary_text,
        "executed_nodes": executed,
    }

workflow = StateGraph(PlanState)
workflow.add_node("fetch_flights", fetch_flights_node)
workflow.add_node("fetch_hotels", fetch_hotels_node)
workflow.add_node("synthesize_itinerary", synthesize_itinerary_node)

workflow.set_entry_point("fetch_flights")
workflow.add_edge("fetch_flights", "fetch_hotels")
workflow.add_edge("fetch_hotels", "synthesize_itinerary")
workflow.add_edge("synthesize_itinerary", END)

graph_app = workflow.compile()

@app.get("/")
async def root():
    return {"message": "TripMate AI Engine is active."}

@app.post("/plan_trip")
async def plan_trip(request_data: TripRequest):
    initial_state: PlanState = {
        "request": request_data.model_dump(),
        "flight_data": {},
        "hotel_data": {},
        "executed_nodes": [],
        "final_itinerary": "",
    }

    final_state = await graph_app.ainvoke(initial_state)
    raw_itinerary = final_state.get("final_itinerary", "")
    clean_itinerary = extract_clean_text(raw_itinerary)

    return {
        "status": "Success",
        "architecture": "LangGraph StateGraph with MCP Tools",
        "executed_nodes": final_state.get("executed_nodes"),
        "flight_data": final_state.get("flight_data"),
        "hotel_data": final_state.get("hotel_data"),
        "final_itinerary": clean_itinerary,
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)