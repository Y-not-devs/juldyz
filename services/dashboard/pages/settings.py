import streamlit as st
import requests

# Fetch current settings
def fetch_settings():
    try:
        response = requests.get("http://localhost:8000/api/core/settings")
        if response.status_code == 200:
            return response.json()
        else:
            st.error("Failed to fetch settings.")
            return {}
    except Exception as e:
        st.error(f"Error fetching settings: {e}")
        return {}

# Update settings
def update_settings(new_settings):
    try:
        response = requests.post("http://localhost:8000/api/core/settings", json=new_settings)
        if response.status_code == 200:
            st.success("Settings updated successfully!")
        else:
            st.error("Failed to update settings.")
    except Exception as e:
        st.error(f"Error updating settings: {e}")

# Settings page
st.title("Settings")
settings = fetch_settings()

if settings:
    instruction = st.text_area("AI Instruction", value=settings.get("instruction", ""))
    if st.button("Save"):
        update_settings({"instruction": instruction})