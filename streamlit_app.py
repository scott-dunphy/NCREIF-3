import streamlit as st
import openai
import requests
import json
import re

# Set your OpenAI API key from the Streamlit secrets.
openai.api_key = st.secrets["OPENAI_API_KEY"]

# A simple mapping from plain language data points to Census API variables.
variable_mapping = {
    "median household income": "B19013_001E",
    "population": "B01003_001E",
    "total population": "B01003_001E",
    "poverty count": "B17001_002E",
    # ... add more mappings as needed
}

def get_geographic_code(state: str) -> str:
    """
    Uses the LLM to convert a U.S. state name into its two-digit FIPS code.
    We prompt the LLM for a concise answer. If the answer isn’t exactly two digits,
    we try to extract it using regex.
    """
    prompt = f"Please provide only the two-digit FIPS code for the U.S. state '{state}'."
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant that returns only the two-digit FIPS code "
                "for a given U.S. state. Do not include any extra text."
            )
        },
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0  # Keep it deterministic!
        )
        code = response.choices[0].message.content.strip()
        # Validate the code: It should be exactly two digits.
        if len(code) == 2 and code.isdigit():
            return code
        else:
            # Attempt to extract two-digit code using regex.
            match = re.search(r"\b(\d{2})\b", code)
            if match:
                return match.group(1)
            else:
                return None
    except Exception as e:
        st.error(f"Error obtaining geographic code: {e}")
        return None

def get_census_data(data_point: str, year: str, state: str):
    """
    Fetch census data for a given data point, year, and state.
    This function relies on the LLM to obtain the FIPS code for the state.
    """
    # Get the FIPS code using the LLM.
    fips = get_geographic_code(state)
    if not fips:
        return {"error": f"Could not obtain FIPS code for state: {state}"}
    
    # Determine the corresponding Census variable using our mapping.
    variable = None
    for key, value in variable_mapping.items():
        if key in data_point.lower():
            variable = value
            break
    if not variable:
        return {"error": f"Data point '{data_point}' not recognized. Consider updating the mapping."}
    
    # Build the Census API URL. We omit the API key since it's not required.
    url = f"https://api.census.gov/data/{year}/acs/acs5"
    params = {
        "get": variable,
        "for": f"state:{fips}"
    }
    
    # Witty aside: Our Census API is as chill as a cucumber—no key required!
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        return {"data": data}
    else:
        return {"error": "Failed to fetch data", "status_code": response.status_code}

# Define the function schema for OpenAI to use with function calling.
functions = [
    {
        "name": "get_census_data",
        "description": "Fetch census data based on a data point, year, and state.",
        "parameters": {
            "type": "object",
            "properties": {
                "data_point": {
                    "type": "string",
                    "description": "The census data point to retrieve, e.g., 'median household income' or 'population'."
                },
                "year": {
                    "type": "string",
                    "description": "The year of the census data, e.g., '2019'."
                },
                "state": {
                    "type": "string",
                    "description": "The U.S. state for which the census data is requested, e.g., 'California'."
                }
            },
            "required": ["data_point", "year", "state"]
        }
    }
]

# Build the Streamlit UI.
st.title("Census Data Query with LLM-Powered Geographic Codes")
st.write("Ask a plain-language question about census data, and I'll fetch the results—thanks to our trusty LLM for translating state names into FIPS codes!")

query = st.text_input("Enter your query about census data:")

if st.button("Submit Query"):
    if query:
        st.write("Analyzing your query and summoning the mighty LLM... ⏳")
        messages = [{"role": "user", "content": query}]
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0613",  # Use a model that supports function calling.
            messages=messages,
            functions=functions,
            function_call="auto"
        )
        message = response["choices"][0]["message"]
        if message.get("function_call"):
            function_name = message["function_call"]["name"]
            try:
                arguments = json.loads(message["function_call"]["arguments"])
            except json.JSONDecodeError:
                st.error("Error decoding function arguments.")
                arguments = {}
            st.write(f"OpenAI decided to call: **{function_name}** with arguments:")
            st.json(arguments)
            if function_name == "get_census_data":
                result = get_census_data(
                    data_point=arguments.get("data_point"),
                    year=arguments.get("year"),
                    state=arguments.get("state")
                )
                st.write("### Census Data Result:")
                st.json(result)
            else:
                st.write("Unknown function called.")
        else:
            st.write("Response from model:")
            st.write(message.get("content", "No content returned."))
    else:
        st.warning("Please enter a query to proceed!")
