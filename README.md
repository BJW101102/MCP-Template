# MCP-Template
a Python starter project for building an MCP (Model Context Protocol) server. It includes a server, a client pool to manage multiple connections safely, and a Jupyter notebook demonstrating how to use the tools and communicate with the AI. The project is structured to make it easy to add your own tools, prompts, and workflows. To get started, clone the repository, install dependencies, run the server, and use the notebook to test and interact with your MCP setup.

**Prerequisites:** 
- Create a virtual environment (conda or python) and activate it
    ```bash
    # Python Virtual Environment (Create)
    python -m venv .venv

    # Activating (Windows)
    .\.venv\Scripts\activate

    # Activating (Linux/MacOS)
    source .venv/bin/activate
    ```

    ```bash
    # Conda Virtual Environment (Create)
    conda create -n myenv python=3.11

    # Activating 
    conda activate myenv
    ```

- pip install the requirements (in the environment)
    ```python
    pip install -r requirements.txt
    ```
- Make sure you have an **Azure client** (or OpenAI; you may need to update the code if new fields are required). Create a `.env` file in the project root directory with the following fields:

    ```bash
    AZURE_API_KEY="Your API Key"
    ENDPOINT="Your Endpoint"
    VERSION="Your OpenAI Version"
    MODEL="Your Azure OpenAI Model"
    ```

# Sources
- Official MCP Documentation: https://modelcontextprotocol.io/docs/getting-started/intro
- Official MCP Python-SDK: https://github.com/modelcontextprotocol/python-sdk