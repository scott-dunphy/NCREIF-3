import os
import json
import time
from urllib.parse import urlparse, parse_qs

import pandas as pd
import requests
import streamlit as st
import openai  # The shiny new OpenAI library

# --- API & Credentials Setup ---
openai.api_key = st.secrets["OPENAI_API_KEY"]

NCREIF_USER = st.secrets["NCREIF_USER"]
NCREIF_PASSWORD = st.secrets["NCREIF_PASSWORD"]

# --- NCREIF API Function ---
def ncreif_api(ptypes: str, cbsas: str = None, begq: str = '20231', endq: str = '20234'):
    """
    Fetch and aggregate data from the NCREIF API.
    
    Quarters must be formatted as YYYYQ.
    """
    aggregated_data = []
    ptypes_list = ptypes.split(",")
    cbsas_list = cbsas.split(",") if cbsas else [None]

    for ptype in ptypes_list:
        for cbsa in cbsas_list:
            url = (
                f"http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=[NPI]=1 and "
                f"[PropertyType]='{ptype}' and [YYYYQ]>{begq} and [YYYYQ]<={endq}"
            )
            if cbsa:
                url += f" and [CBSA]='{cbsa}'"
                group_by = "[PropertyType],[CBSA],[YYYYQ]"
            else:
                group_by = "[PropertyType],[YYYYQ]"
            url += (
                f"&GroupBy={group_by}&Format=json&UserName={NCREIF_USER}&password={NCREIF_PASSWORD}"
            )

            st.write(f"Fetching data from: {url}")  # Because transparency is magical.
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()['NewDataSet']['Result1']
                aggregated_data.extend(data)
            except requests.exceptions.RequestException as e:
                st.error(f"Error fetching data for {ptype} and CBSA {cbsa}: {e}")
                return None
            except (KeyError, TypeError) as e:
                st.error(
                    f"Error parsing JSON response for {ptype} and CBSA {cbsa}: {e}. "
                    f"Raw Response: {response.text if 'response' in locals() else 'N/A'}"
                )
                return None

    return aggregated_data

# --- Census API Function ---
def census_pop(cbsa: str, year: str):
    """
    Fetch Census ACS Population data for a given CBSA and year.
    """
    url = (
        f"https://api.census.gov/data/{year}/acs/acs5?"
        f"get=B01003_001E,NAME&for=metropolitan%20statistical%20area/"
        f"micropolitan%20statistical%20area:{cbsa}"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return int(data[1][0]) if data and len(data) > 1 else None
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching census data for CBSA {cbsa} in {year}: {e}")
        return None
    except (IndexError, TypeError) as e:
        st.error(
            f"Error parsing census data for CBSA {cbsa} in {year}: {e}. "
            f"Raw Response: {r.text if 'r' in locals() else 'N/A'}"
        )
        return None

# --- OpenAI ChatCompletion Setup ---
system_message = {
    "role": "system",
    "content": (
        "TAKE A DEEP BREATH AND GO STEP-BY-STEP!\n"
        "[Background]\n"
        "You are an expert at Statistics and calculating Time Weighted Returns using the Geometric Mean calculation.\n\n"
        "Given data for multiple property types and/or CBSAs, calculate and compare the Time Weighted Returns "
        "for each property type and CBSA.\n\n"
        "You also have access to Census population data for CBSAs."
    )
}

# Define our function call specifications
functions = [
    {
        "name": "ncreif_api",
        "description": (
            "Generates an API call for the NCREIF API. "
            "O = Office, R = Retail, I = Industrial, A = Apartments. "
            "Quarters are formatted as YYYYQ. When asked for 1-year returns as of a certain date, "
            "use the trailing four quarters from the as of date. For example, the quarters used in the "
            "calculation for the 1-year return as of 3Q 2023 would be 4Q 2022, 1Q 2023, 2Q 2023, and 3Q 2023. "
            "The begq would be 20223 and the endq would be 20233."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ptypes": {
                    "type": "string",
                    "description": "Comma-separated property types selected (e.g., 'O,R,I,A').",
                },
                "cbsas": {
                    "type": "string",
                    "description": "Comma-separated list of Census CBSA codes (e.g., '19100,12060').",
                },
                "begq": {
                    "type": "string",
                    "description": "Beginning quarter in the format YYYYQ (e.g., 20231).",
                },
                "endq": {
                    "type": "string",
                    "description": "Ending quarter in the format YYYYQ (e.g., 20234).",
                },
            },
            "required": ["ptypes", "begq", "endq"],
        },
    },
    {
        "name": "census_pop",
        "description": "Generates an API call for the Census ACS Population using CBSA codes.",
        "parameters": {
            "type": "object",
            "properties": {
                "cbsa": {
                    "type": "string",
                    "description": "Census CBSA code",
                },
                "year": {
                    "type": "string",
                    "description": "The year of the Census ACS survey.",
                },
            },
            "required": ["cbsa", "year"],
        },
    },
]

# --- Chat Runner Class ---
class ChatRunner:
    """
    A simple runner to maintain conversation context with the OpenAI ChatCompletion API.
    """
    def __init__(self):
        self.conversation_history = [system_message]

    def run(self, query: str):
        # Append the user's query to the conversation
        self.conversation_history.append({"role": "user", "content": query})
        response = openai.ChatCompletion.create(
            model="gpt-4-0613",
            messages=self.conversation_history,
            functions=functions,
            function_call="auto",
            temperature=0.7,
        )
        # Append the assistant's response to the conversation
        self.conversation_history.append(response["choices"][0]["message"])
        return response

# --- Streamlit Front-End ---
def main():
    st.title("Time Weighted Returns Assistant")
    st.markdown(
        "Welcome to the witty assistant for calculating Time Weighted Returns and accessing Census data. "
        "Simply type your query below and let the magic unfold!"
    )

    # Initialize ChatRunner in session state
    if "chat_runner" not in st.session_state:
        st.session_state.chat_runner = ChatRunner()

    # Create a text input for user queries
    query = st.text_input("Enter your query here", value="", key="query_input")
    
    # When the user clicks 'Send Query'
    if st.button("Send Query"):
        if query.strip():
            with st.spinner("Thinking..."):
                st.session_state.chat_runner.run(query)
            # Clear the input field after sending
            st.session_state.query_input = ""
        else:
            st.warning("Please enter a query!")

    # Option to reset the conversation
    if st.button("Reset Conversation"):
        st.session_state.chat_runner = ChatRunner()
        st.experimental_rerun()

    st.write("### Conversation History")
    # Display the conversation history
    for message in st.session_state.chat_runner.conversation_history:
        role = message.get("role", "unknown")
        content = message.get("content", "")
        if role == "user":
            st.markdown(f"**User:** {content}")
        elif role == "assistant":
            st.markdown(f"**Assistant:** {content}")
        elif role == "system":
            st.markdown(f"**System:** {content}")
        else:
            st.markdown(f"**{role.capitalize()}:** {content}")

if __name__ == "__main__":
    main()
