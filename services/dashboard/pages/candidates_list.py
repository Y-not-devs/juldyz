import streamlit as st
import requests

# Fetch candidate data from the backend
def fetch_candidates():
    try:
        response = requests.get("http://localhost:8000/api/core/candidates")
        if response.status_code == 200:
            candidates = response.json()
            # Filter and map only useful data
            return [
                {
                    "id": candidate["id"],
                    "name": f"{candidate['first_name']} {candidate['last_name']}",
                    "email": candidate["email"],
                    "program": candidate["program_applied"],
                    "score": candidate.get("honors_raw", "N/A"),
                    "activities": candidate.get("activities_raw", "N/A"),
                }
                for candidate in candidates
            ]
        else:
            st.error("Failed to fetch candidates.")
            return []
    except Exception as e:
        st.error(f"Error fetching candidates: {e}")
        return []

# Display candidates
st.title("Candidates List")
candidates = fetch_candidates()

if candidates:
    for candidate in candidates:
        st.subheader(candidate["name"])
        st.write(f"Email: {candidate['email']}")
        st.write(f"Program: {candidate['program']}")
        st.write(f"Score: {candidate['score']}")
        st.write(f"Activities: {candidate['activities']}")
        st.write("---")
else:
    st.write("No candidates found.")