from openai import OpenAI
import json
import pandas as pd
import requests
import streamlit as st
import os
import base64
from urllib.parse import urlparse, parse_qs
import time
import streamlit as st

client = OpenAI()
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]


def ncreif_api(ptype):
    url = f"http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=[NPI]=1%20and%20[PropertyType]=%27{ptype}%27 and [YYYYQ]>20154&GroupBy=[PropertyType],[YYYYQ]&Format=json&UserName=sdunphy@metlife.com&password=password"
    #url = f"http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=[NPI]=1%20and%20[YYYYQ]>20154&GroupBy=[PropertyType],[YYYYQ]&Format=json&UserName=sdunphy@metlife.com&password=password"
    r = requests.get(url)
    return r.json()['NewDataSet']['Result1']

assistant = client.beta.assistants.create(
    instructions="""
            TAKE A DEEP BREATH AND GO STEP-BY-STEP!
            [Background]
            You are an expert at Statistics and calculating Time Weighted Returns using the Geometric 
            Mean calculation.
            
            """,
    model="gpt-4-turbo-preview",
    tools=[
        {"type": "code_interpreter"},
        {"type": "function",
         "function": {
             "name": "ncreif_api",
             "description": "Generates an API call for the NCREIF API.O = Office, R = Retail, I = Industrial, A = Apartments ",
             "parameters": {
                 "type": "object",
                 "properties": {
                     "ptype": {
                         "type": "string",
                         "enum": ["O", "R", "I", "A"],
                         "description": "Comma-separated property types selected (e.g., 'O,R,I,A').",
                     },
                 },        
             }
         }
        }
    ]
)




import json
import time

class ThreadRunner:
    def __init__(self, client, available_functions=None):
        self.client = client
        self.available_functions = available_functions or {'ncreif_api': ncreif_api}
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
            instructions="""
            You are an expert data analyst tasked with calculating geometric means for income returns, capital returns, and total returns grouped by property type from a given dataset. The dataset contains the following columns:

            PropertyType: The type of property (e.g., A, R)
            YYYY: The year
            Q: The quarter (1-4)
            IncomeReturn: The income return for the given property type, year, and quarter
            CapitalReturn: The capital return for the given property type, year, and quarter
            TotalReturn: The total return (income return + capital return) for the given property type, year, and quarter
            Props: The number of properties for the given property type, year, and quarter
            
            Your task is to calculate the following geometric means:
            
            1. 1-year geometric mean for each return type (IncomeReturn, CapitalReturn, TotalReturn) for property type A as of the most recent quarter (3Q 2023 in the given data).
            2. 3-year geometric mean for each return type (IncomeReturn, CapitalReturn, TotalReturn) for property type A as of the most recent quarter (3Q 2023 in the given data).
            
            To calculate the geometric mean, use the formula:
            Geometric Mean = Product(1 + Values)^(1/n)
            where n is the number of values.
            """
        )
        
        while True:
            time.sleep(1)
            run = self.client.beta.threads.runs.retrieve(thread_id=self.thread.id, run_id=run.id)
            
            if run.status == 'requires_action':
                tool_outputs = []
                
                for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                    call_id = tool_call.id
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Use a custom function or return raw data
                    if function_name in self.available_functions:
                        function_response = self.available_functions[function_name](**function_args)
                        output = json.dumps(function_response) if not isinstance(function_response, str) else function_response
                    else:
                        output = "Raw data placeholder or fetch logic here"
                    
                    tool_outputs.append({
                        "tool_call_id": call_id,
                        "output": output
                    })
                
                self.client.beta.threads.runs.submit_tool_outputs(
                    thread_id=self.thread.id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )
                
            elif run.status == 'completed':
                self.messages = self.client.beta.threads.messages.list(thread_id=self.thread.id)
                return self.messages
            
            elif run.status in ['queued', 'in_progress', 'cancelling']:
                continue
            
            else:
                print(f"Unhandled Run Status: {run.status}")
                break


# Initialize your ThreadRunner with the client
runner = ThreadRunner(client)

import streamlit as st

def run_query_and_display_results():
    # Access the query from st.session_state
    query = st.session_state.query if 'query' in st.session_state else ''
    if query:
        # Assuming 'runner' is already initialized and run_thread is properly defined
        messages = runner.run_thread(query)  
        if messages:
            result = messages.data[0].content[0].text.value
            # Update session state with the results
            st.session_state['results'] = result
        else:
            # Clear results if there are none
            st.session_state['results'] = "No results found."
    else:
        # Clear or set a default message when there's no query
        st.session_state['results'] = "Please enter a query."

st.title('AI NCREIF QUERY TOOL w/ Analytics')

# Text input for the query. The on_change function updates session state but doesn't directly display results.
query = st.text_input("Enter your query:", key="query", on_change=run_query_and_display_results)

# Display results here, after the input box
if 'results' in st.session_state:
    st.write(st.session_state['results'])




