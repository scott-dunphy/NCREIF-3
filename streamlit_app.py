import os
import json
import time
from urllib.parse import urlparse, parse_qs

import pandas as pd
import requests
import streamlit as st
from openai import OpenAI

# Initialize OpenAI client and secrets
client = OpenAI()
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
NCREIF_USER = st.secrets["NCREIF_USER"]
NCREIF_PASSWORD = st.secrets["NCREIF_PASSWORD"]

# NCREIF API function with improved flexibility and error handling
def ncreif_api(ptypes, cbsas=None, begq='20231', endq='20234'):
    aggregated_data = []
    ptypes_list = ptypes.split(",")
    cbsas_list = cbsas.split(",") if cbsas else [None]

    for ptype in ptypes_list:
        for cbsa in cbsas_list:
            url = f"http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=[NPI]=1 and [PropertyType]='{ptype}' and [YYYYQ]>{begq} and [YYYYQ]<={endq}"
            if cbsa:
                url += f" and [CBSA]='{cbsa}'"
                group_by = "[PropertyType],[CBSA],[YYYYQ]"
            else:
                group_by = "[PropertyType],[YYYYQ]"
            url += f"&GroupBy={group_by}&Format=json&UserName={NCREIF_USER}&password={NCREIF_PASSWORD}"

            st.write(f"Fetching data from: {url}")  # Display the URL being fetched
            try:
                response = requests.get(url, timeout=10)  # Add a timeout for requests
                response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
                data = response.json()['NewDataSet']['Result1']
                aggregated_data.extend(data)
            except requests.exceptions.RequestException as e:
                st.error(f"Error fetching data for {ptype} and CBSA {cbsa}: {e}") # Display error in Streamlit
                return None # Return None to signal failure
            except (KeyError, TypeError) as e:  # Handle potential JSON parsing errors
                st.error(f"Error parsing JSON response for {ptype} and CBSA {cbsa}: {e}. Raw Response: {response.text if 'response' in locals() else 'N/A'}")
                return None
    return aggregated_data


# Census API function with error handling and data extraction
def census_pop(cbsa, year):
    url = f"https://api.census.gov/data/{year}/acs/acs5?get=B01003_001E,NAME&for=metropolitan%20statistical%20area/micropolitan%20statistical%20area:{cbsa}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return int(data[1][0]) if data and len(data) > 1 else None # Handle cases where data is empty or missing
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching census data for CBSA {cbsa} in {year}: {e}")
        return None
    except (IndexError, TypeError) as e:
        st.error(f"Error parsing census data for CBSA {cbsa} in {year}: {e}. Raw Response: {r.text if 'r' in locals() else 'N/A'}")
        return None


# Assistant creation (no changes needed here)
assistant = client.beta.assistants.create(
    instructions="""
        TAKE A DEEP BREATH AND GO STEP-BY-STEP!
        [Background]
        You are an expert at Statistics and calculating Time Weighted Returns using the Geometric
        Mean calculation.

        Given data for multiple property types and/or CBSAs, calculate and compare the Time Weighted Returns
        for each property type and CBSA. 

        You also have access to Census population data for CBSAs.
    """,
    model="gpt-4-turbo-preview",
    tools=[
        {"type": "code_interpreter"},
        {"type": "function",
         "function": {
             "name": "ncreif_api",
             "description": """Generates an API call for the NCREIF API.O = Office, R = Retail, I = Industrial, A = Apartments. Quarters are formatted as YYYYQ.
                                When asked for 1-year returns as of a certain date, you will use the trailing four quarters from the as of date. For example, the
                                quarters used in the calculation for the 1-year return as of 3Q 2023 would be 4Q 2022, 1Q 2023, 2Q 2023, and 3Q 2023. The begq would be
                                20223 and the endq would be 20233. """,
             "parameters": {
                 "type": "object",
                 "properties": {
                     "ptypes": {
                         "type": "string",
                         "description": "Comma-separated property types selected (e.g., 'O,R,I,A').",
                     },
                     "cbsas": {
                         "type": "string",
                         "description": "Comma-separated list of Census CBSA codes for NCREIF returns or property type (e.g. '19100, 12060').",
                     },
                     "begq": {
                         "type": "string",
                         "description": "Beginning quarter for the data requested in the format YYYYQ. MUST be formatted as YYYYQ (e.g. 3Q 2023 = 20233",
                     },
                     "endq": {
                         "type": "string",
                         "description": "Ending quarter for the data requested in the format YYYYQ. This would also be the 'as of' quarter. MUST be formatted as YYYYQ (e.g. 3Q 2023 = 20233",
                     },
                 },
             }
         }
        },
        {"type": "function",
         "function": {
             "name": "census_pop",
             "description": "Generates an API call for the Census ACS Population using CBSA codes. ",
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
             }
         }
        }
    ]
)


class ThreadRunner:
    def __init__(self, client, available_functions=None):
        self.client = client
        self.available_functions = available_functions or {'ncreif_api': ncreif_api, 'census_pop': census_pop}
        self.thread = None
        self.messages = []

    def create_thread(self):
        self.thread = self.client.beta.threads.create()

    def run_thread(self, query):
        if not self.thread:
            self.create_thread()

        self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=query
        )

        run = self.client.beta.threads.runs.create(
            thread_id=self.thread.id,
            assistant_id=assistant.id,
            instructions=
            """
            You are an expert data analyst tasked with calculating geometric means for income returns, capital returns, and total returns grouped by property type from a given dataset. The dataset contains the following columns:

            PropertyType: The type of property (e.g., A, R)
            YYYY: The year
            Q: The quarter (1-4)
            IncomeReturn: The income return for the given property type, year, and quarter
            CapitalReturn: The capital or appreciation return for the given property type, year, and quarter
            TotalReturn: The total return (income return + capital return) for the given property type, year, and quarter
            Props: The number of properties for the given property type, year, and quarter
            
            Your task is to calculate the following geometric means.
            
            To calculate the geometric mean, use the formula:
            Geometric Mean = [Product(1 + Values)^(1/n)]**4-1
            where n is the number of observations.
            """
        )
