import os
import json
import time
import requests
import streamlit as st
from typing import Optional, Dict, Any

# We'll keep these imports in case you expand your app:
# from io import BytesIO
# from pathlib import Path
# from urllib.parse import urlparse, parse_qs
# import base64
# import glob

# 1. Grab your secrets from Streamlit
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
NCREIF_USER = st.secrets["NCREIF_USER"]
NCREIF_PASSWORD = st.secrets["NCREIF_PASSWORD"]

# 2. Define your data-fetching functions
def ncreif_api(
    ptypes: str, 
    cbsas: Optional[str] = None, 
    begq: str = '20231', 
    endq: str = '20234'
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
                    data = response.json()['NewDataSet']['Result1']
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
            
            # Rate limiting, so NCREIF doesn't get grumpy
            time.sleep(1)
    
    return aggregated_data

def census_pop(cbsa: str, year: str) -> int:
    """
    Fetch Census ACS Population data using a CBSA code and a survey year.
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

# 3. Import or define your LangChain–esque components
from langchain.schema import LLMResult
from langchain.agents import FunctionEnvelope, FunctionTool

# “ChatOpenAI” can come from langchain.chat_models if you want real calls:
# But you have a custom import, so adjust as needed.
from langchain_openai import ChatOpenAI

# Initialize your LLM (this part is optional until you do more advanced logic)
llm = ChatOpenAI(model_name="gpt-4-turbo")

# 4. Wrap the functions as “tools”
ncreif_tool = FunctionTool(
    func=ncreif_api,
    description="Generate an API call for the NCREIF API. Accepts comma-separated property types, optional cbsas, and begq/endq."
)
census_tool = FunctionTool(
    func=census_pop,
    description="Fetch Census ACS Population data by CBSA code and year."
)

# 5. A simple agent function: always call the NCREIF tool
def agent_func(llm_result: LLMResult, tools: Dict[str, FunctionEnvelope]) -> str:
    """
    A super-simple function that always calls the NCREIF tool,
    using the user's query as 'ptypes'.
    """
    # For real usage, you'd parse llm_result to figure out user intent,
    # or run more LLM logic. Here, we just interpret the query as the ptypes.
    return tools["ncreif_tool"].run(
        ptypes=llm_result.llm_output["message"]["actions"]["tool_function"],
        cbsas=None,
        begq='20231',
        endq='20234'
    )

# 6. A basic class to hold the LLM and tools; not a full “Agent” from standard LangChain,
#    but enough to illustrate hooking it up in Streamlit:
class SimpleAgent:
    def __init__(self, llm, tools, agent_func):
        """
        We'll store tools in a dict keyed by name so we can do tools["ncreif_tool"] 
        or tools["census_tool"] inside agent_func.
        """
        self.llm = llm
        self._tools = {
            "ncreif_tool": FunctionEnvelope(
                function=tools[0].func,
                description=tools[0].description
            ),
            "census_tool": FunctionEnvelope(
                function=tools[1].func,
                description=tools[1].description
            ),
        }
        self.agent_func = agent_func

    def run(self, query: str) -> Any:
        # In principle, you'd ask your LLM to produce a function call here.
        # For demonstration, we just stash 'query' in a pseudo-LLMResult.
        dummy_actions = {"tool_function": query}
        llm_output = {"message": {"actions": dummy_actions}}
        llm_result = LLMResult(generations=[], llm_output=llm_output)
        return self.agent_func(llm_result, self._tools)

# Instantiate our super-minimal agent
agent = SimpleAgent(llm=llm, tools=[ncreif_tool, census_tool], agent_func=agent_func)

# 7. Streamlit UI
st.title("AI NCREIF QUERY TOOL w/ Analytics (and Terrible Jokes)")

def run_query_and_display_results():
    query = st.session_state.get("query", "")
    if query:
        try:
            # Our agent 'interprets' the query as the property types
            result = agent.run(query)
            st.session_state['results'] = result
        except Exception as e:
            st.session_state['results'] = f"Error: {e}"
    else:
        st.session_state['results'] = "Please enter a query."

# Provide a text input so the user can specify e.g. "O,R,I" for property types
st.text_input("Enter your property types (comma-separated):", 
              key="query", on_change=run_query_and_display_results)

# Display the results
if 'results' in st.session_state:
    st.write(st.session_state['results'])
