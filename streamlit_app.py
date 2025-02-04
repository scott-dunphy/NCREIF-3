import os
import json
import time
from urllib.parse import urlparse, parse_qs

import pandas as pd
import requests
import streamlit as st
import openai  # The new and improved OpenAI library

# Set up our API key (because even modern wizards need magic words)
openai.api_key = st.secrets["OPENAI_API_KEY"]

NCREIF_USER = st.secrets["NCREIF_USER"]
NCREIF_PASSWORD = st.secrets["NCREIF_PASSWORD"]


def ncreif_api(ptypes: str, cbsas: str = None, begq: str = '20231', endq: str = '20234'):
    """
    Fetches and aggregates data from the NCREIF API. Quarters must be formatted as YYYYQ.
    (Our code is so fresh, even the API URLs get a facelift.)
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

            st.write(f"Fetching data from: {url}")  # Because transparency is the best policy.
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


def census_pop(cbsa: str, year: str):
    """
    Fetches Census ACS Population data for the given CBSA and year.
    (Because who doesn't love some census trivia with their API calls?)
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


# --- ChatCompletion API Setup ---
# Our system prompt now sets the scene like a director before the big show.
system_message = {
    "role": "system",
    "content": (
        "TAKE A DEEP BREATH AND GO STEP-BY-STEP!\n"
        "[Background]\n"
        "You are an expert at Statistics and calculating Time Weighted Returns using the Geometric Mean calculation.\n\n"
        "Given data for multiple property types and/or CBSAs, calculate and compare the Time Weighted Returns\n"
        "for each property type and CBSA. \n\n"
        "You also have access to Census population data for CBSAs."
    )
}

# Define our function call specifications with descriptions so the assistant knows what spell to cast
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


def run_chat(query: str, conversation_history=None):
    """
    Sends a chat request to OpenAI's ChatCompletion API while preserving conversation history.
    (Think of it as the conversational version of your favorite multi-step recipe.)
    """
    if conversation_history is None:
        conversation_history = [system_message]
    conversation_history.append({"role": "user", "content": query})
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",  # Use your favorite model — the latest and greatest!
        messages=conversation_history,
        functions=functions,
        function_call="auto",
        temperature=0.7,
    )
    conversation_history.append(response["choices"][0]["message"])
    return response, conversation_history


class ChatRunner:
    """
    A simple runner class to maintain conversation context with the OpenAI ChatCompletion API.
    (Because even brilliant minds need a good running partner.)
    """
    def __init__(self):
        self.conversation_history = [system_message]

    def run(self, query: str):
        self.conversation_history.append({"role": "user", "content": query})
        response = openai.ChatCompletion.create(
            model="gpt-4-0613",
            messages=self.conversation_history,
            functions=functions,
            function_call="auto",
            temperature=0.7,
        )
        self.conversation_history.append(response["choices"][0]["message"])
        return response


# --- Example usage ---
# Uncomment the following lines to try it out in your Streamlit app (or any other environment)
# chat_runner = ChatRunner()
# response = chat_runner.run(
#     "Calculate the geometric mean returns for property type A in CBSA 12345 for the last year. "
#     "Remember to use the trailing four quarters."
# )
# st.write(response)
