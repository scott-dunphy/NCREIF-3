import os
import json
import time
import requests
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import streamlit as st
import base64
import glob
from typing import Optional, Dict, Any

# Set your API keys and credentials from Streamlit secrets
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
NCREIF_USER = st.secrets["NCREIF_USER"]
NCREIF_PASSWORD = st.secrets["NCREIF_PASSWORD"]

def ncreif_api(ptypes: str, cbsas: Optional[str] = None, begq: str = '20231', endq: str = '20234') -> list:
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
                f"http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=[NPI]=1 "
                f"and [PropertyType]='{ptype}' and [YYYYQ]>{begq} and [YYYYQ] <= {endq}"
            )
            if cbsa:
                url += f" and [CBSA]='{cbsa}'"
                group_by = "[PropertyType],[CBSA],[YYYYQ]"
            else:
                group_by = "[PropertyType],[YYYYQ]"
            
            url += f"&GroupBy={group_by}&Format=json&UserName={NCREIF_USER}&password={NCREIF_PASSWORD}"
            st.write(url)
            
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    data = response.json()['NewDataSet']['Result1']
                    aggregated_data.extend(data)
                else:
                    st.error(f"Failed to fetch data for property type {ptype} and CBSA {cbsa}")
                    continue
            except Exception as e:
                st.error(f"Error fetching data: {e}")
                continue
            
            # Add rate limiting
            time.sleep(1)
    
    return aggregated_data

def census_pop(cbsa: str, year: str) -> int:
    """
    Fetch Census ACS Population data using a CBSA code and survey year.
    """
    url = (
        f"https://api.census.gov/data/{year}/acs/acs5?"
        f"get=B01003_001E,NAME&for=metropolitan%20statistical%20area/"
        f"micropolitan%20statistical%20area:{cbsa}"
    )
    try:
        r = requests.get(url)
        r.raise_for_status()
        return int(r.json()[1][0])
    except Exception as e:
        st.error(f"Error fetching census data: {e}")
        return 0

# Import the latest LangChain components
from langchain.schema import LLMResult
from langchain.llms import ChatOpenAI
from langchain.agents import (
    Agent,
    FunctionEnvelope,
    FunctionTool,
    get_function_tools
)

# Initialize the LLM
llm = ChatOpenAI(model_name="gpt-4-turbo")

# Define the tools using FunctionTool
ncreif_tool = FunctionTool(
    func=ncreif_api,
    description="Generates an API call for the NCREIF API. Accepts comma-separated property types and optional comma-separated CBSA codes along with begq and endq parameters."
)

census_tool = FunctionTool(
    func=census_pop,
    description="Fetches Census ACS Population data using a CBSA code and a survey year."
)

# Create an agent with these tools
async def agent_func(
    llm_result: LLMResult,
    tools: Dict[str, FunctionEnvelope]
) -> str:
    # The core logic of the agent
    # This function will decide which tool to call based on the user's input
    # and return the appropriate response
    return await tools["ncreif_tool"].run(
        ptypes=llm_result.message["actions"]["tool_function"],
        cbsas=None,
        begq='20231',
        endq='20234'
    )

agent = Agent(
    llm=llm,
    tools=[ncreif_tool, census_tool],
    agent_func=agent_func
)

# --- Streamlit UI ---
st.title('AI NCREIF QUERY TOOL w/ Analytics')

def run_query_and_display_results():
    query = st.session_state.get("query", "")
    if query:
        try:
            # Run the agent with the query
            result = agent.run(query)
            st.session_state['results'] = result
        except Exception as e:
            st.session_state['results'] = f"Error: {e}"
    else:
        st.session_state['results'] = "Please enter a query."

# Text input for the query; on_change updates session state and runs the query.
st.text_input("Enter your query:", key="query", on_change=run_query_and_display_results)

# Display results if available.
if 'results' in st.session_state:
    st.write(st.session_state['results'])
