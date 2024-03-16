from openai import OpenAI

client = OpenAI()
import json
import pandas as pd
import requests
import streamlit as st
import os
import base64
from urllib.parse import urlparse, parse_qs

os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

def ncreif_api(url):
    print(url)
    r = requests.get(url)
    
    return pd.DataFrame(r.json()['NewDataSet']['Result1']), url #r.json() #df


def run_conversation(prompt):
    
    # Step 1: send the conversation and available functions to GPT
    #prompt = input("What is your query?: ")
    messages = [{"role": "user", "content": f"{prompt}"},
                {"role": "system", "content": """
                 Take a deep breath and go step-by-step.
                 1. You are running queries against an API. 
                 2. If the user asks about returns then exclude the 'select' parameter from the function
                 / api request and use KPI=Returns instead; otherwise create the select parameter as defined. 
                   Where and Group by clauses should not end with 'and'.
                 3. Take the input parameters provided.
                 4. Map any synonyms to their respective API terms using the provided dictionary.
                 5. Construct the select statement in SQL style; however, any parameters in the group statement should not be in the select statement.
                 6.When 'as of' is used it refers to a where statement for YYYYQ. 
                 7.YYYYQ is numeric and should not have quotes. 
                 Here are example prompts and the URL that should be passed to the function. Be sure to include all where statements as appropriate.
                Prompt: Give me historical returns by property type?
                Answer: http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=NPI=1&GroupBy=[PropertyType],[YYYYQ]&Format=json&UserName=sdunphy@metlife.com&password=password
                
                Prompt: What are historical returns by property type?
                Answer: http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=NPI=1&GroupBy=[PropertyType],[YYYYQ]&Format=json&UserName=sdunphy@metlife.com&password=password
                
                Prompt: Calculate property returns in the Phoenix market by property type?
                Answer: http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=NPI=1%20and%20[CBSAName]=%27AZ-Phoenix-Mesa-Scottsdale%27&GroupBy=[PropertyType],YYYYQ&Format=json&UserName=sdunphy@metlife.com&password=password
                
                Prompt: What are returns in the phoenix market by property type as of 2Q 2023?
                Answer: http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=NPI=1%20and%20[CBSAName]=%27AZ-Phoenix-Mesa-Scottsdale%27%20and%20YYYYQ=20232&GroupBy=[PropertyType]&Format=json&UserName=sdunphy@metlife.com&password=password
                
                Prompt: Calculate apartment property returns in the Phoenix market.
                Answer: http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=NPI=1%20and%20[CBSAName]=%27AZ-Phoenix-Mesa-Scottsdale%27%20and%20[PropertyType]=%27A%27&GroupBy=[YYYYQ],[PropertyType]&Format=json&UserName=sdunphy@metlife.com&password=password
                
                Prompt: What are historical apartment returns in the Phoenix market?
                Answer: http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=NPI=1%20and%20[CBSAName]=%27AZ-Phoenix-Mesa-Scottsdale%27%20and%20[PropertyType]=%27A%27&GroupBy=[YYYYQ],[PropertyType]&Format=json&UserName=sdunphy@metlife.com&password=password
                
                Prompt: What are historical retail returns in the Phoenix market?
                Answer: http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=NPI=1%20and%20[CBSAName]=%27AZ-Phoenix-Mesa-Scottsdale%27%20and%20[PropertyType]=%27R%27&GroupBy=[YYYYQ],[PropertyType]&Format=json&UserName=sdunphy@metlife.com&password=password
                
                Prompt: Show me office returns by market as of 2Q 2023.
                Answer: http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=NPI=1%20and%20[PropertyType]=%27O%27%20and%20YYYYQ=20232&GroupBy=[CBSAName]&Format=json&UserName=sdunphy@metlife.com&password=password
                
                Prompt: Calculate market value and net operating income by property type.
                Answer: http://www.ncreif-api.com/API.aspx?SELECT=sum(NOI)%20as%20NOI,%20sum(MV)%20as%20MarketValue&Where=NPI=1&GroupBy=YYYYQ,[PropertyType]&Format=JSON&UserName=sdunphy@metlife.com&password=password
                
                Prompt: Calculate the sum of NOI and Market Value and the property count by market and property type as of December 31, 2022.
                Answer: http://www.ncreif-api.com/API.aspx?SELECT=sum(NOI)%20as%20NOI,%20sum(MV)%20as%20MarketValue,%20count(*)%20as%20PropCount&Where=NPI=1%20and%20[YYYYQ]=20224&GroupBy=[CBSAName],[PropertyType]&Format=JSON&UserName=sdunphy@metlife.com&password=password
                
                Prompt: Calculate the volatility of property type returns between 1Q 2010 and 4Q 2020.
                Answer: http://www.ncreif-api.com/API.aspx?SELECT=stdev(IncRet)%20as%20IncomeReturnVol,%20stdev(AppRet)%20as%20AppReturnVol,%20stdev(TotRet)%20as%20TotalRetVol&Where=NPI=1%20and%20[YYYYQ]%20%3E=20101%20and%20[YYYYQ]%20%3C=%2020204&GroupBy=[PropertyType]&Format=JSON&UserName=sdunphy@metlife.com&password=password

                Prompt: calculate the volatility of office returns between 1q 2010 and 4q 2020.
                Answer: http://www.ncreif-api.com/API.aspx?SELECT=stdev(IncRet)%20as%20IncomeReturnVol,%20stdev(AppRet)%20as%20AppReturnVol,%20stdev(TotRet)%20as%20TotalRetVol&Where=NPI=1%20and%20[YYYYQ]%20%3E=20101%20and%20[YYYYQ]%20%3C=%2020204%20and%20[PropertyType]=%27O%27&GroupBy=[PropertyType]&Format=JSON&UserName=sdunphy@metlife.com&password=password

                Prompt: Calculate the volatility of office returns between 1Q 2010 and 4Q 2020.
                Answer: http://www.ncreif-api.com/API.aspx?SELECT=stdev(IncRet)%20as%20IncomeReturnVol,%20stdev(AppRet)%20as%20AppReturnVol,%20stdev(TotRet)%20as%20TotalRetVol&Where=NPI=1%20and%20[YYYYQ]%20%3E=20101%20and%20[YYYYQ]%20%3C=%2020204%20and%20[PropertyType]=%27O%27&GroupBy=[PropertyType]&Format=JSON&UserName=sdunphy@metlife.com&password=password
                    
                Prompt: Calculate the sum of NOI, MV, and NRA for apartments by quarter.
                Answer: http://www.ncreif-api.com/API.aspx?SELECT=sum(NOI)%20as%20NOI,%20sum(MV)%20as%20MarketValue,%20sum(NRA)%20as%20NRA&Where=[PropertyType]=%27A%27&GroupBy=[YYYYQ]&Format=json&UserName=sdunphy@metlife.com&password=password
                 
                Prompt: Calculate the standard deviation of market total returns between 1Q 2020 and 2Q 2023.
                Answer: http://www.ncreif-api.com/API.aspx?SELECT=stdev(TotRet)%20as%20std_dev&Where=NPI=1 and [YYYYQ]%20%3E=20201%20and%20[YYYYQ]%20%3C=%2020232&GroupBy=[CBSAName]&Format=JSON&UserName=sdunphy@metlife.com&password=password
                    
                Prompt: Summarize office returns by Year Built and quarter.
                Answer: http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=NPI=1%20and%20[PropertyType]%20=%27O%27%20&GroupBy=[YrBuiltorLastRen],[YYYYQ]&Format=json&UserName=sdunphy@metlife.com&password=password
                
                Prompt: Show me returns by Property type and Year Built as of 3Q 2023.
                Answer: http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=NPI=1%20and%20[YYYYQ]=20233&GroupBy=[YrBuiltorLastRen],[YYYYQ],[PropertyType]&Format=json&UserName=sdunphy@metlife.com&password=password

                Prompt: Show me returns by Property type as of 3Q 2023 where Year Built is after 2015.
                Answer: http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=NPI=1%20and%20[YYYYQ]=20233%20and%20[YrBuiltorLastRen]>2015&GroupBy=[YYYYQ],[PropertyType]&Format=json&UserName=sdunphy@metlife.com&password=password

                Prompt: What are retail returns by Property Type and Subtype between 1Q 2014 and 4Q 2018?
                Answer: http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=NPI=1 and [PropertyType]='R' and [YYYYQ]>=20141 and [YYYYQ]<=20184&GroupBy=[YYYYQ],[PropertyType],[PropertySubType]&Format=json&UserName=sdunphy@metlife.com&password=password
                
                Prompt: What are historical office and retail returns?
                Answer: http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=NPI=1 and [PropertyType] IN ('R','O')&GroupBy=[YYYYQ],[PropertyType]&Format=json&UserName=sdunphy@metlife.com&password=password

                Prompt: What are office returns in phoenix and dallas?
                Answer: http://www.ncreif-api.com/API.aspx?KPI=Returns&Where=NPI=1 and [CBSAName] IN ('AZ-Phoenix-Mesa-Scottsdale','TX-Dallas-Plano-Irving') and [PropertyType]='O'&GroupBy=[YYYYQ],[CBSAName]&Format=json&UserName=sdunphy@metlife.com&password=password

                Prompt: Calculate Same Store NOI by property type between 1Q 2000 and 4Q 2007.
                Answer: http://www.ncreif-api.com/API.aspx?Select=sum(NOI)%20as%20NOI&Where=NPI=1%20and%20[YYYYQ]>=20001%20AND%20[YYYYQ]%20<=20074%20AND%20[StartDate]<20001%20AND%20[EndDate]>=20074&GroupBy=%5BPropertyType%5D,%5BYYYYQ%5D&Format=json&UserName=sdunphy@metlife.com&password=password
                
                 synonyms = {
                    'Market Value': 'MV',
                    'Net Operating Income':'NOI',
                    'Year Built':'YrBuiltorLastRen',
                    'Region':'Region',
                    'Capital Expenditures':'CapEx',
                    'CapEx':'CapEx',
                    'Life Cycle':'LifeCycle',
                    'Square Feet':'NRA',
                    'Net Rentable Area':'NRA',
                    'Occupancy':'PercentLeased',
                    'State':'State',
                    'Joint Venture':'JV',
                    'Division':'Division',
                    'Subtype':'PropertySubType',
                    'Fund Type':'FundType',
                    'Fund':'FundType',
                    'ODCE':'D',
                    'Start Date':'StartDate',
                    'End Date':'EndDate',
                    'Denominator':'denom',
                    'Prior Market Value':'MVLag1',
                    'Capex':'Capex',
                    'Capital Expenditures':'capex',
                    'NOI':'NOI',
                    'Square Feet':'SqFt',
                    'Market':'CBSAName',
                    'Property Type':'PropertyType',
                    'Period':'YYYYQ',
                    'Quarter':'YYYYQ',
                    'Office':'O',
                    'Retail':'R',
                    'Industrial':'I',
                    'Apartments':'A',
                    'Hotels':'H',
                    'New York':'NY-NJ-New York-Jersey City-White Plains',
                    'Los Angeles':'CA-Los Angeles-Long Beach-Glendale',
                    'Washington DC':'DC-VA-MD-WV-Washington-Arlington-Alexandria',
                    'Riverside':'CA-Riverside-San Bernardino-Ontario',
                    'Chicago':'IL-Chicago-Naperville-Arlington Heights',
                    'Dallas':'TX-Dallas-Plano-Irving',
                    'Seattle':'WA-Seattle-Bellevue-Everett',
                    'San Francisco':'CA-San Francisco-Redwood City-South San Francisco',
                    'Atlanta':'GA-Atlanta-Sandy Springs-Roswell',
                    'Boston':'MA-Boston',
                    }
                 """ 
                 
                 }]
    functions = [
        {
            "name": "ncreif_api",
            "description": """ 
                                Generates a URL for the NCREIF API 
                            """,
           "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL for the API call" ,
                    },
                },
                     
            },
        }
    ]

    assistant = client.beta.assistants.create(
          instructions="You are an investment analyst. When asked a math question, write and run code to answer the question.",
          model="gpt-4-turbo-preview",
          tools=[
              {"type": "code_interpreter"}
              {"type": "function",
               "function": {
                   "name": "ncreif_api",
                   "description": "Generates an API call for the NCREIF API",
                   "parameters":
                   {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL for the API call" ,
                    },
                },        
            }
               }
                   ]
        )
    
    response = client.chat.completions.create(model="gpt-4-1106-preview",
            temperature = .5,
            messages=messages,
            functions=functions,
            function_call="auto")
    
    response_message = response.choices[0].message

    if response_message.function_call:
        available_functions = {
            "ncreif_api": ncreif_api,
        }  
        function_name = response_message.function_call.name
        fuction_to_call = available_functions[function_name]
        function_args = json.loads(response_message.function_call.arguments)
        function_response = fuction_to_call(
            url=function_args.get("url"),
        )

        messages.append(response_message) 
        messages.append(
            {
                "role": "function",
                "name": function_name,
                "content": function_response,
            }
        )
        
        #second_response = client.chat.completions.create(
        #model="gpt-3.5-turbo-1106",
        #messages=messages,
        #        )  # get a new response from the model where it can see the function response
        #st.write(function_response)
        return function_response
        
st.set_page_config(page_title='AI-POWERED NCREIF QUERY TOOL')
st.title('AI-POWERED NCREIF QUERY TOOL')

write_value = "Example: What are historical office returns in Dallas?"

query_input = st.text_input("Enter your query: ")

df = pd.DataFrame()
url = ''
if query_input:
    try:
        df,url = run_conversation(query_input)
        write_value = df
    except:
        write_value = "Error processing query. Please try again."
   
    
st.write(write_value)

if len(df) > 0:
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()  # Encode to bytes and then decode to string
    href = f'<a href="data:file/csv;base64,{b64}" download="ncreif_query.csv">Download CSV File</a>'
    
    # Provide a download link for the CSV
    st.markdown(href, unsafe_allow_html=True)
    
    # ...


# Ensure url is not None or empty before trying to parse it
if url != '':
    st.header("API URL and Parameters")
    st.write(url[:len(url)-47] + "\n")
    # Parse the URL
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    # Extract and summarize the SELECT, KPI, Where, and GroupBy statements
    select_params = query_params.get('SELECT', [])
    kpi_params = query_params.get('KPI', [])
    where_params = query_params.get('Where', [])
    groupby_params = query_params.get('GroupBy', [])

    # Summarize SELECT parameters
    if select_params:
        select_summary = select_params[0].split(',')
        st.write("SELECT Statement Parameters:")
        for param in select_summary:
            st.write(f"- {param.strip()}")
    elif kpi_params:
        st.write(f"KPI Parameter: {kpi_params[0]}")
    else:
        st.write("No SELECT or KPI parameters found.")

    # Summarize Where parameters
    if where_params:
        where_summary = where_params[0].split('and')
        st.write("\nWhere Statement Parameters:")
        for param in where_summary:
            st.write(f"- {param.strip()}")
    else:
        st.write("No Where statement parameters found.")

    # Summarize GroupBy parameters
    if groupby_params:
        st.write(f"\nGroupBy Statement Parameters:\n- {groupby_params[0]}")
    else:
        st.write("No GroupBy statement parameters found.")
else:
    st.write("")
