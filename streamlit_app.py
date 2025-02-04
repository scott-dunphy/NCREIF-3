import os
import json
import time
import requests
import streamlit as st
from urllib.parse import urlparse, parse_qs

# Set credentials from Streamlit secrets
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
NCREIF_USER = st.secrets["NCREIF_USER"]
NCREIF_PASSWORD = st.secrets["NCREIF_PASSWORD"]

def ncreif_api(ptypes, cbsas=None, begq='20231', endq='20234'):
    """
    Generate an API call for the NCREIF API.
    ptypes: Comma-separated property types (e.g., "O,R,I,A").
    cbsas: Optional comma-separated CBSA codes.
    begq: Beginning quarter (formatted as YYYYQ).
    endq: Ending quarter (formatted as YYYYQ; also the 'as of' quarter).
    """
    aggregated_data = []
    ptypes_list = ptypes.split(",")
    if cbsas is not None:
        cbsas_list = cbsas.split(",")
    else:
        cbsas_list = [None]
    for ptype in ptypes_list:
        for cbsa in cbsas_list:
            url = (
                f"http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=[NPI]=1 "
                f"and [PropertyType]='{ptype}' and [YYYYQ]>{begq} and [YYYYQ] <= {endq}"
            )
            if cbsa is not None:
                url += f" and [CBSA]='{cbsa}'"
                group_by = "[PropertyType],[CBSA],[YYYYQ]"
            else:
                group_by = "[PropertyType],[YYYYQ]"
            url += f"&GroupBy={group_by}&Format=json&UserName={NCREIF_USER}&password={NCREIF_PASSWORD}"
            st.write(url)
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()['NewDataSet']['Result1']
                aggregated_data.extend(data)
            else:
                st.error(f"Failed to fetch data for property type {ptype} and CBSA {cbsa}")
    return aggregated_data

def census_pop(cbsa, year):
    """
    Fetch Census ACS Population data using a CBSA code and a survey year.
    """
    url = (
        f"https://api.census.gov/data/{year}/acs/acs5?"
        f"get=B01003_001E,NAME&for=metropolitan%20statistical%20area/"
        f"micropolitan%20statistical%20area:{cbsa}"
    )
    r = requests.get(url)
    return int(r.json()[1][0])

# --- Updated LangChain Integration ---
# We now use LangChain’s agent framework with tools.
from langchain.chat_models import ChatOpenAI
from langchain.agents import Tool, initialize_agent, AgentType

# Initialize the chat model (using GPT-4, for example)
llm = ChatOpenAI(model_name="gpt-4")

# Define tools for the agent
tool_ncreif = Tool(
    name="ncreif_api",
    func=ncreif_api,
    description=(
        "Generates an API call for the NCREIF API. Accepts comma-separated property types "
        "and optional comma-separated CBSA codes along with begq and endq parameters. "
        "For example, for a 1-year return as of 3Q 2023, use begq='20223' and endq='20233'."
    )
)

tool_census = Tool(
    name="census_pop",
    func=census_pop,
    description="Fetches Census ACS Population data using a CBSA code and a survey year."
)

# Create an agent that supports function calling using the latest OpenAI integration.
agent_executor = initialize_agent(
    tools=[tool_ncreif, tool_census],
    llm=llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    verbose=True
)

# --- Streamlit UI ---
st.title('AI NCREIF QUERY TOOL w/ Analytics')

def run_query_and_display_results():
    query = st.session_state.get("query", "")
    if query:
        try:
            # Run the agent executor; it will call the appropriate tools as needed.
            result = agent_executor.run(query)
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
