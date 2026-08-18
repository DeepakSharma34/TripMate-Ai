import os
import streamlit as st
import requests

# Combine host and port for the orchestrator
ORCH_HOST = os.getenv("ORCHESTRATOR_HOST", "localhost")
ORCH_PORT = os.getenv("ORCHESTRATOR_PORT", "8000")
ORCHESTRATOR_URL = f"http://{ORCH_HOST}:{ORCH_PORT}"

st.title("✈️ TripMate AI Travel Concierge")
st.write("Plan your dream trip within budget using our multi-agent AI microservice architecture!")


st.sidebar.header("Trip Parameters")
origin = st.sidebar.text_input("Origin Airport", "BOM")
destination = st.sidebar.text_input("Destination Airport", "GOI")
departure_date = st.sidebar.date_input("Departure Date")
return_date = st.sidebar.date_input("Return Date")
passengers = st.sidebar.number_input("Passengers", min_value=1, max_value=10, value=2)
budget_inr = st.sidebar.number_input("Total Budget (INR)", min_value=5000, max_value=500000, value=30000, step=5000)
duration_days = st.sidebar.number_input("Duration (Days)", min_value=1, max_value=30, value=5)

if st.button("Generate AI Itinerary 🚀"):
    with st.spinner("Fetching live flights, finding hotels, and drafting your itinerary..."):
        payload = {
            "origin": origin,
            "destination": destination,
            "departure_date": str(departure_date),
            "return_date": str(return_date),
            "passengers": passengers,
            "budget_inr": budget_inr,
            "duration_days": duration_days
        }
        
        try:
            response = requests.post("http://127.0.0.1:8000/plan_trip", json=payload)
            if response.status_code == 200:
                data = response.json()
                st.success("Itinerary generated successfully!")
                
                
                st.markdown("### Your Custom Itinerary")
                st.markdown(data.get("final_itinerary", ""))
                
                
            else:
                st.error(f"Error from server: {response.text}")
        except Exception as e:
            st.error(f"Could not connect to backend. Is main.py running? Error: {e}")