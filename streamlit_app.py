import streamlit as st
import openai
import requests
import json
import re
from tenacity import retry, wait_random_exponential, stop_after_attempt

# Set your OpenAI API key (make sure it's defined in .streamlit/secrets.toml)
openai.api_key = st.secrets["OPENAI_API_KEY"]

# ------------------------------------------------------------
# Utility: Retry-enabled chat completion request (cookbook style)
# ------------------------------------------------------------
@retry(wait=wait_random_exponential(multiplier=1, max=40), stop=stop_after_attempt(3))
def chat_completion_request(messages, functions=None, function_call="auto", model="gpt-4o"):
    """
    Call the Chat Completion API with retry logic.
    'functions' holds our function specifications and 'function_call' can be "auto", "none", or forced.
    """
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        functions=functions,
        function_call=function_call,
    )
    return response

# ------------------------------------------------------------
# Helper: Get FIPS Code and Geography Type via LLM (generic geographic code lookup)
# ------------------------------------------------------------
def get_geographic_code(geography: str) -> dict:
    """
    Use the LLM to get the FIPS code for the given U.S. geography.
    The assistant is prompted to return a JSON object with keys "code" and "geography".
    For example, if the input is "California", a valid output might be:
      {"code": "06", "geography": "state"}
    """
    prompt = (
        f"Please provide the FIPS code for the U.S. geography '{geography}'. "
        "Return your answer as a JSON object with keys 'code' and 'geography'. "
        "For example: {\"code\": \"06\", \"geography\": \"state\"}. "
        "Do not include any extra text."
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant that returns the FIPS code and geographic type "
                "for a given U.S. geography in JSON format. Do not include any extra text."
            )
        },
        {"role": "user", "content": prompt}
    ]
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=messages,
            temperature=0  # Keep responses deterministic.
        )
        content = response.choices[0].message.content.strip()
        try:
            data = json.loads(content)
            if "code" in data and "geography" in data:
                return data
            else:
                st.error("JSON does not contain expected keys 'code' and 'geography'.")
                return None
        except json.JSONDecodeError:
            st.error("Failed to parse JSON output for FIPS code.")
            return None
    except Exception as e:
        st.error(f"Error obtaining geographic code: {e}")
        return None

# ------------------------------------------------------------
# Helper: Map plain language data points to Census API variables.
# (Extend this dictionary as needed.)
# ------------------------------------------------------------
variable_mapping = {
    "median household income": "B19013_001E",
    "population": "B01003_001E",
    "total population": "B01003_001E",
    "poverty count": "B17001_002E",
}

# ------------------------------------------------------------
# Main function: Fetch Census data
# ------------------------------------------------------------
def get_census_data(data_point: str, year: str, geography: str):
    """
    Fetches Census data by first obtaining the FIPS code (and its geographic type) via LLM,
    mapping the plain language data point to a Census variable, and then calling the Census API.
    """
    # Use the LLM to get the FIPS code and geographic type.
    geo_data = get_geographic_code(geography)
    if not geo_data:
        return {"error": f"Could not obtain FIPS code for geography: {geography}"}
    
    fips = geo_data.get("code")
    geo_type = geo_data.get("geography")  # e.g., "state", "county", etc.
    
    # Map the data point to a Census variable.
    variable = None
    for key, val in variable_mapping.items():
        if key in data_point.lower():
            variable = val
            break
    if not variable:
        return {"error": f"Data point '{data_point}' not recognized. Try updating the mapping."}
    
    # Build the Census API URL (no API key required).
    url = f"https://api.census.gov/data/{year}/acs/acs1"
    
    # Construct the query parameters.
    # NOTE: The Census API expects different parameters depending on the geography.
    # Here we assume that the geography type can be used directly.
    params = {
        "get": variable,
        "for": f"{geo_type}:{fips}"
    }
    
    # Witty aside: Our Census API is as chill as a Sunday morning—no key needed!
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return {"geography": geo_data, "data": response.json()}
    else:
        return {"error": "Failed to fetch data", "status_code": response.status_code}

# ------------------------------------------------------------
# Define our function specification ("tool") for function calling.
# ------------------------------------------------------------
functions = [
    {
        "name": "get_census_data",
        "description": "Fetch census data based on a data point, year, and geography.",
        "parameters": {
            "type": "object",
            "properties": {
                "data_point": {
                    "type": "string",
                    "description": "The census data point to retrieve (e.g., 'median household income' or 'population')."
                },
                "year": {
                    "type": "string",
                    "description": "The year of the census data, e.g., '2019'."
                },
                "geography": {
                    "type": "string",
                    "description": "The U.S. geography (e.g., 'California' for state-level or 'Los Angeles County' for county-level data)."
                },
            },
            "required": ["data_point", "year", "geography"],
        }
    }
]

# ------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------
st.title("Census Data Query with Function Calling Framework")
st.write("Enter your query about Census data (for example: *'What was the median household income in California in 2019?'*)")

query = st.text_input("Your Query:")

if st.button("Submit Query"):
    if query:
        st.write("Processing your query and consulting our function-calling intern... ⏳")
        # Prepare initial conversation.
        messages = [{"role": "user", "content": query}]
        
        # Call the Chat Completion API with our function specifications.
        response = chat_completion_request(
            messages,
            functions=functions,
            function_call="auto"  # Let the model decide whether to use our function.
        )
        message = response.choices[0].message
        
        # If the model decided to call a function, process it.
        if message.get("function_call"):
            function_name = message["function_call"]["name"]
            try:
                arguments = json.loads(message["function_call"]["arguments"])
            except json.JSONDecodeError as e:
                st.error(f"Error decoding function arguments: {e}")
                arguments = {}
            
            st.write(f"Model decided to call: **{function_name}** with arguments:")
            st.json(arguments)
            
            if function_name == "get_census_data":
                result = get_census_data(
                    data_point=arguments.get("data_point"),
                    year=arguments.get("year"),
                    geography=arguments.get("geography")
                )
                st.write("### Census Data Result:")
                st.json(result)
            else:
                st.error("Unknown function called.")
        else:
            st.write("Response from model:")
            st.write(message.get("content", "No content returned."))
    else:
        st.warning("Please enter a query!")
