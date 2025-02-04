import os
import time
import requests
import streamlit as st
from typing import Optional

# from io import BytesIO
# from pathlib import Path
# from urllib.parse import urlparse, parse_qs
# import base64
# import glob

# 1. Grab your secrets from Streamlit
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
NCREIF_USER = st.secrets["NCREIF_USER"]
NCREIF_PASSWORD = st.secrets["NCREIF_PASSWORD"]

##############################
# Data-fetching functions
##############################

def ncreif_api(
    ptypes: str, 
    cbsas: Optional[str] = None, 
    begq: str = "20231", 
    endq: str = "20234"
) -> list:
    """
    Generate an API call for the NCREIF API.
    ptypes: Comma-separated property types (e.g., "O,R,I,A").
    cbsas: Optional comma-separated CBSA codes.
    begq: Beginning quarter (formatted as YYYYQ).
    endq: Ending quarter (formatted as YYYYQ; also the 'as of' quarter).
    """
    aggregated_data = []
    ptypes_list = ptypes.split(",")
    cbsas_list = cbsas.split(",") if cbsas else [None]
    
    for ptype in ptypes_list:
        for cbsa in cbsas_list:
            url = (
                "http://www.ncreif-api.com/API.aspx?"
                "KPI=Returns"
                f"&Where=[NPI]=1 and [PropertyType]='{ptype}' "
                f"and [YYYYQ]>{begq} and [YYYYQ]<={endq}"
            )
            if cbsa:
                url += f" and [CBSA]='{cbsa}'"
                group_by = "[PropertyType],[CBSA],[YYYYQ]"
            else:
                group_by = "[PropertyType],[YYYYQ]"
            
            url += (
                f"&GroupBy={group_by}"
                f"&Format=json&UserName={NCREIF_USER}&password={NCREIF_PASSWORD}"
            )
            st.write(f"NCREIF API URL: {url}")

            try:
                response = requests.get(url)
                if response.status_code == 200:
                    data = response.json()["NewDataSet"]["Result1"]
                    aggregated_data.extend(data)
                else:
                    st.error(
                        f"Failed to fetch data for property type '{ptype}' "
                        f"and CBSA '{cbsa}'. Status code: {response.status_code}"
                    )
                    continue
            except Exception as e:
                st.error(f"Error fetching data: {e}")
                continue
            
            # Rate limiting
            time.sleep(1)
    
    return aggregated_data

def census_pop(cbsa: str, year: str) -> int:
    """
    Fetch Census ACS Population data using a CBSA code and a survey year.
    """
    url = (
        f"https://api.census.gov/data/{year}/acs/acs5?"
        f"get=B01003_001E,NAME"
        f"&for=metropolitan%20statistical%20area/"
        f"micropolitan%20statistical%20area:{cbsa}"
    )
    try:
        r = requests.get(url)
        r.raise_for_status()
        return int(r.json()[1][0])
    except Exception as e:
        st.error(f"Error fetching census data: {e}")
        return 0

##############################
# LangChain + Tools
##############################

# If you have an older LangChain, you may only have 'Tool' available in:
#   from langchain.tools import Tool
# We'll rely on that simple approach here.

from langchain.tools import Tool
# For an LLM, if needed:
# from langchain.chat_models import ChatOpenAI

ncreif_tool = Tool(
    name="ncreif_api",
    func=ncreif_api,
    description="Call the NCREIF API. Provide ptypes, optional cbsas, and begq/endq."
)

census_tool = Tool(
    name="census_pop",
    func=census_pop,
    description="Fetch Census ACS Population data using a CBSA code and a survey year."
)

# NOTE: If you want an actual agent with a chain-of-thought deciding which tool
# to use, you'd add more code here. For now, we'll just call 'ncreif_tool' 
# directly from Streamlit.

##############################
# Streamlit UI
##############################
st.title("AI NCREIF QUERY TOOL (No Fancy Agents)")

def run_query_and_display_results():
    # We'll treat user input as ptypes, for example "O,R,I" 
    query = st.session_state.get("query", "")
    if query.strip():
        try:
            # We simply call the "ncreif_api" tool function
            # You could parse the query or do more advanced logic here:
            results = ncreif_tool.run(ptypes=query)
            st.session_state["results"] = results
        except Exception as e:
            st.session_state["results"] = f"Error: {e}"
    else:
        st.session_state["results"] = "Please enter property types in the box."

st.text_input(
    "Enter comma-separated property types (e.g. O,R,I,A):",
    key="query", 
    on_change=run_query_and_display_results
)

if "results" in st.session_state:
    st.write(st.session_state["results"])
