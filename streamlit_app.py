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
    # ... (instructions, model, tools)
)

# ThreadRunner class (no changes needed here)
class ThreadRunner:
    # ... (code remains the same)

# Initialize ThreadRunner
runner = ThreadRunner(client)

# Streamlit app
st.title('AI NCREIF QUERY TOOL w/ Analytics')

# Input section
col1, col2 = st.columns(2) # Create two columns for layout
with col1:
    ptypes_input = st.text_input("Property Types (e.g., O,R,I,A):", value="O,R,I,A")
with col2:
    cbsas_input = st.text_input("CBSA Codes (e.g., 19100,12060):")

col3, col4 = st.columns(2)
with col3:
  begq_input = st.text_input("Begin Quarter (YYYYQ):", value="20231")
with col4:
  endq_input = st.text_input("End Quarter (YYYYQ):", value="20234")


query = st.text_area("Enter your query:", height=150) # Larger text area
go_button = st.button("Run Query")  # Explicit button to trigger query

# Query execution and results display
if go_button:
    if not query:
        st.warning("Please enter a query.")
    else:
        try:
            with st.spinner("Running query..."): # Display a spinner while running
                messages = runner.run_thread(query)
            if messages:
                result = messages.data[0].content[0].text.value # Access the text value correctly
                st.write("## Results") # More prominent heading for results
                st.write(result) # Display the result
            else:
                st.error("An error occurred during query execution. Check the logs above.") # More specific error message
        except Exception as e:
            st.exception(f"A general error occurred: {e}") # Display the full exception details for debugging
