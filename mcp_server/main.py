import os
from openai import AzureOpenAI
from mcp.server.fastmcp import FastMCP
from internet_search import get_text_from_search
from dotenv import load_dotenv
load_dotenv(dotenv_path='./.env')

# IMPORTANT: If you plan on using an OpenAI client, or any other client the credentials have to be passed to instantiate the client.
# for demo purposes, we will use a persistent client tied to our environment variables. 
openai_client = AzureOpenAI(
    api_key=os.getenv('AZURE_API_KEY'),
    api_version=os.getenv('VERSION'),
    azure_endpoint=os.getenv('ENDPOINT'),
)

MODEL = os.getenv('MODEL')

# IMPORTANT: By default, the streamble-http transport layer is open w/ HTTP not HTTPS. Be careful when deploying
mcp = FastMCP("Demo", host='127.0.0.1', port=4000) 

# IMPORTANT: The descriptions provided for the tools WILL be seen by the LLM when it begins to select a tool
@mcp.tool(description=
    """Adds two numbers"""
) 
def add(a: int, b: int) -> int: 
    return a + b 

@mcp.tool(description=
"""Tell's a family-friendly joke about the desired topic"""
) 
def tell_joke(topic: str) -> str: 
    prompt = f"Tell me a short, family-friendly joke about {topic or 'anything'}."
    response = openai_client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=50
    )
    joke = response.choices[0].message.content.strip()
    return joke

@mcp.tool(description=
    """
    Searches the internet via Dux Distributed Global Search, and answers a user's question/query.
    This tool will handle most of the user queries that require additional context.
    """
) 
def search_internet_and_answer(query: str) -> str: 
    sys_prompt = f"""
    INSTRUCTIONS:  
    You are a helpful AI assistant designed to answer users' questions using the context provided.  
    Your main audience is **Gen Z college students**, so keep your answers **full, clear, and casual**, feel free to use slang, memes, or relatable language.  
    Always answer **fully**, give examples if needed, and format your responses in **Markdown** for easy reading.
    """
    
    # Step 1: Search the internet and gather the needed content
    print("[1]: Fetching from Internet....")
    internet_content = get_text_from_search(query)
    
    # Step 2: Pass the context to the model 
    print(f"[2]: Passing Context...")
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "system", "content": f"CONTEXT: {internet_content}"},
        {"role": "user", "content": query}
    ]
    
    # Step 3: Invoke the model
    print(f"[3]: Invoking LLM ...")
    response = openai_client.chat.completions.create(
        model=MODEL,
        messages=messages
    )
    
    # Step 4: Send the final answer back to the client
    print(f"[4]: Answer Generated, sending to client!")
    answer = response.choices[0].message.content.strip()
    return answer

if __name__ == "__main__": 
    rf"""
    Run Command (From project-root directory):  uv run .\mcp-server\main.py
    """
    mcp.run(transport='streamable-http')

