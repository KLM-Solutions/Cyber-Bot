import streamlit as st
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
import psycopg2


# Access your API keys
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
# Database connection parameters
db_params = {
    "dbname": "Gradient",
    "user": "postgres",
    "password": "test",
    "host": "localhost",
    "port": "5432"
}

TABLE_NAME = 'cyber'
EMBEDDING_MODEL = "text-embedding-ada-002"

# List of all columns
ALL_COLUMNS = [
    "ID", "eventDtgTime", "alerts", "displayTitle", "instantAnalytics", "detailedText", 
    "msgPrecs", "unit", "size", "embedHtml", "dataSources", "snippetText", "contentLink", 
    "description", "imageDescription", "reportSummary", "authorName", "timeReportCompleted", 
    "attachment", "latitude", "securityLevels", "imagereSourceLink", "eventDtg", "status", 
    "users", "name", "sessions", "fiscalStatus", "sentimentSummary", "sourceOrg", 
    "dateCreated", "active", "responseSummary", "comparisonCommunitiesCountries", 
    "activity", "applications", "url", "timeZones", "location", "longitude", "dateModified", 
    "pedigrees", "gistComment", "tag", "geoCode", "time", "ReportRouted", "rteToOrg", 
    "copyReportToOrg", "sourceOrganization", "coordinates", "image1", "image2", "image3", 
    "image4", "image5", "numEmailsSent", "lastEmailDate", "reportDtg", "metadata", 
    "eventOrganizations", "classification", "assetIPs", "sitrepTemplate", "industry", 
    "networkSegmentList", "approvedDate", "incident", "sendEmail", "newFormat", 
    "duMapping", "jsonTag", "createdFrom", "integrationData", "mtti", "mttd", "mttr", 
    "oldEventDate", "org_event_name"
]

# Update the DEFAULT_SYSTEM_INSTRUCTION variable as follows:

DEFAULT_SYSTEM_INSTRUCTION = """You are an AI assistant specialized in cybersecurity incident analysis. Your task is to analyze the given query and related cybersecurity data, and provide a focused, relevant response. Follow these guidelines:

1. Analyze the user's query carefully to understand the specific cybersecurity concern or question.

2. Search through all provided data columns to find information relevant to the query.

3. Use the following analysis framework as appropriate to the query:
   - Threat Assessment: Identify and assess potential threats or security issues.
   - Incident Analysis: Analyze relevant incidents, looking for patterns or connections.
   - Temporal Analysis: Consider timing of events if relevant to the query.
   - Geographical Considerations: Analyze geographical patterns or risks if location data is provided and relevant.
   - User and System Involvement: Assess involvement of users, systems, or networks as pertinent to the query.
   - Data Source Evaluation: Consider the reliability and relevance of data sources if this impacts the analysis.
   - Compliance and Policy: Mention compliance issues or policy violations only if directly relevant.

4. Provide actionable recommendations  to the query and the data found.

5. Structure your response to directly address the user's query, using only the most relevant parts of the analysis framework.

6. Be concise and to the point. Do not list out or explicitly mention these guidelines in your response.

7. If certain aspects of the analysis are not relevant to the query, omit them from your response.

Your response should be informative, actionable, and directly relevant to the specific query and the data provided. Focus on giving insights and recommendations that are most pertinent to the user's question."""

# The rest of the code remains the same
def query_similar_records(query_text, k=5):
    embeddings = OpenAIEmbeddings(
        openai_api_key=OPENAI_API_KEY,
        model=EMBEDDING_MODEL
    )
    query_embedding = embeddings.embed_query(query_text)
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()
    try:
        cur.execute(f"""
        SELECT * FROM {TABLE_NAME}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """, (query_embedding, k))
        results = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in results]
    except Exception as e:
        st.error(f"An error occurred during similarity search: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def process_query(query, similar_records, system_instruction):
    llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, model_name="gpt-4o-mini")
    
    template = ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        ("human", """
        Query: {query}

        Related Records:
        {records}

        Please provide a detailed analysis and recommendations based on all this information, 
        following the guidelines provided in the system instructions.
        """)
    ])

    chain = LLMChain(llm=llm, prompt=template)
    
    records_text = ""
    for record in similar_records:
        records_text += "Record:\n"
        for col in ALL_COLUMNS:
            if col in record and record[col]:
                records_text += f"{col}: {record[col]}\n"
        records_text += "\n"

    response = chain.run(query=query, records=records_text)
    return response

def main():
    st.title("Cybersecurity Incident Query System")

    # Sidebar for system instructions
    with st.sidebar:
        st.subheader("System Instructions")
        if st.button("View/Edit Instructions"):
            if 'show_instructions' not in st.session_state:
                st.session_state.show_instructions = False
            st.session_state.show_instructions = not st.session_state.show_instructions

        if 'show_instructions' in st.session_state and st.session_state.show_instructions:
            if 'system_instruction' not in st.session_state:
                st.session_state.system_instruction = DEFAULT_SYSTEM_INSTRUCTION

            custom_instruction = st.text_area("Modify the system instructions here:", 
                                              value=st.session_state.system_instruction, 
                                              height=300)
            
            if st.button("Update Instructions"):
                st.session_state.system_instruction = custom_instruction
                st.success("System instructions updated successfully!")

        # Display whether custom instructions are in use
        if 'system_instruction' in st.session_state and st.session_state.system_instruction != DEFAULT_SYSTEM_INSTRUCTION:
            st.info("Custom instructions are currently in use.")
        else:
            st.info("Default instructions are in use.")

    # Main area for query input and results
    query = st.text_input("Enter your cybersecurity query:")

    if query:  # Process query as soon as it's entered
        with st.spinner("Processing your query..."):
            similar_records = query_similar_records(query)
            if similar_records:
                response = process_query(query, similar_records, st.session_state.get('system_instruction', DEFAULT_SYSTEM_INSTRUCTION))
                
                st.subheader("Analysis and Recommendations:")
                st.write(response)
                
                st.subheader("Similar Records (Key Information):")
                for record in similar_records:
                    st.write("---")
                    for col in ["ID", "eventDtgTime", "alerts", "displayTitle", "incident"]:
                        if col in record and record[col]:
                            st.write(f"{col}: {record[col]}")
            else:
                st.warning("No similar records found for the given query.")

if __name__ == "__main__":
    main()