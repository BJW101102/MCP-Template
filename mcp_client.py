import aiohttp
import json
import uuid
import time
import asyncio
from aiohttp import ClientSession, ClientResponse

JSONRPC_VERSION = "2.0"

# Accepting both layers: STDIO & Streamable HTTP
BASIC_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

SEPARATOR = "__"

class McpConnectionError(Exception):
    """Raised when MCP client cannot reconnect within the allowed timeframe."""

class McpClientPool:
    """
    Keeps multiple aiohttp.ClientSession instances alive
    and lets you call JSON-RPC 2.0 methods on different MCP servers.
    """

    def __init__(self):
        self.all_tools = []
        self._clients: dict[
            str: dict[ # name
                str: ClientSession, # session
                str: str, # base_url
                str: str] # session_id
            ] = {}        
        
    async def add_client(self, name: str, base_url: str, **session_kwargs):
        """
        Create a persistent client session bound to a specific MCP server.
        `base_url` is the full JSON-RPC endpoint for that server.
        """
        if name in self._clients:
            raise ValueError(f"Client '{name}' already exists")
        session = ClientSession(**session_kwargs)
        session_id = await self._initialize_session(session, base_url)
        self._clients[name] = {
            'session': session,
            'base_url': base_url,
            'session_id': session_id
        }
        tools = await self.list_tools(name)
        self.all_tools.extend(tools)  

    async def list_tools(self, name: str) -> list[dict]:
        """
        Retrieves the tools from an MCP Server.
        """
        try:
            method = 'tools/list'
            fmt_tools = []
            client = self._clients[name]
            session: ClientSession = client['session']
            base_url = client['base_url']
            session_id = client['session_id']
        
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session_id
            }
            payload = {
                "jsonrpc": JSONRPC_VERSION,
                "id": str(uuid.uuid4()),
                "method": method,
                "params": {},
            }
            
            response = await self._post(session, base_url, headers=headers, payload=payload)
            ctype = response.headers.get('Content-Type')
            data = await self._parse_response(ctype=ctype, response=response)
            # Getting the first index for streaming responses
            if ctype == 'text/event-stream':
                data = data[0]
            
            tools = data['result']['tools']
            print(
                f"WARNING: To avoid name collisions, the character {SEPARATOR!r} is used as a separator."
                f" When creating tool IDs (server{SEPARATOR}tool), always split using this same separator"
                f" to recover the server and tool name correctly."
            )
            for t in tools:
                tool_name = t["name"]
                tool_key = f"{name}{SEPARATOR}{tool_name}"
                fmt_tools.append({
                    'name': tool_key,
                    'description': t['description'],
                    'parameters': t['inputSchema']
                })
            return fmt_tools
        except McpConnectionError:
            await self._reconnect(name)
            return await self.list_tools(name)
        
    async def call(
        self,
        name: str,
        method: str,
        params: dict | list | None = {},
        request_id: str | None = str(uuid.uuid4()),
    ):
        """
        Perform a single JSON-RPC 2.0 call to the chosen MCP server.
        """
        
        try:
            if name not in self._clients:
                raise KeyError(f"No client named '{name}'")
            
            
            client = self._clients[name]
            
            session: ClientSession = client['session']
            base_url = client['base_url']
            session_id = client['session_id']
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session_id
            }
            payload = {
                "jsonrpc": JSONRPC_VERSION,
                "id": request_id,
                "method": method,
                "params": params,
            }
            response = await self._post(session, base_url, headers=headers, payload=payload)
            ctype = response.headers.get('Content-Type')
            data = await self._parse_response(ctype=ctype, response=response)
            return data
        except McpConnectionError:
            await self._reconnect(name)
            return await self.call(name, method, params, request_id)

    async def close_all(self):
        """
        Gracefully close all sessions—call this on application shutdown.
        """
        for client in self._clients.values():
            session: ClientSession = client['session']
            await session.close()
            
    async def _initialize_session(self, session: ClientSession, base_url: str) -> str:
        """
        Create a persistent client session bound to a specific MCP server.
        """
        # Since we are using a custom client, we need to properly initialize the JSON-RPC handshake.
        # - StackOverFlow: https://stackoverflow.com/questions/79550897/mcp-server-always-get-initialization-error
        # - Lifecycle: http://modelcontextprotocol.io/specification/draft/basic/lifecycle
        # - GitHub: https://github.com/modelcontextprotocol/python-sdk/issues/423
        
        # Step 1: Send initial payload to the server to start a session
        # - This is th "session request" part of the handshake.
        init_payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "tools": True,
                    "resources": True,
                    "prompts": True
                },
                "clientInfo": {
                    "name": "example-client",
                    "version": "0.1.0"
                }
            }
        }
        response = await self._post(session, base_url, payload=init_payload) # Step 1
        session_id = response.headers.get('mcp-session-id')
        
        # Step 2: Notify the server that the client has initialized
        # - This is the "session confirmation" part of the handshake.
        s_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": session_id
        }
        noti_payload = {"jsonrpc":"2.0","method":"notifications/initialized"}
        await self._post(session, base_url, headers=s_headers, payload=noti_payload)
        return session_id
        
    async def _reconnect(self, name: str, timeout: int =30):
        """
        Attempts to reconnecting to the server for `timeout` seconds, then raises error.
        """
        client = self._clients.get(name)
        
        print("Reconnecting!")
        if not client:
            raise KeyError(f"No client named '{name}'")

        base_url = client["base_url"]

        start = time.time()
        while time.time() - start < timeout:
            try:
                # Close old session if still open
                old_session: ClientSession = client["session"]
                if not old_session.closed:
                    await old_session.close()

                new_session = ClientSession()
                session_id = await self._initialize_session(new_session, base_url)

                self._clients[name] = {
                    "session": new_session,
                    "base_url": base_url,
                    "session_id": session_id,
                }
                print("Reconnected | New Connection has been established")
                return  # ✅ Success
            except Exception as e:
                await asyncio.sleep(2)  # retry delay

        raise McpConnectionError(f"Failed to reconnect client '{name}' after {timeout} seconds")
            
    async def _post(self, session: aiohttp.ClientSession, url: str, payload: dict, headers: dict=BASIC_HEADERS) -> ClientResponse:
        try:
            async with session.post(
                url,
                json=payload,
                headers=headers
                ) as resp:
                # Read and buffer the response body.
                # aiohttp response content is a one-time stream; if you don’t
                # read it here, later attempts to access it (e.g., in _parse_response)
                # may fail or return empty data.
                raw_body = await resp.text()
                if resp.status != 200:
                    # This status is usually raised durning initialization
                    if resp.status == 202:
                        return None
                    else:
                        raise RuntimeError(f"Initialize failed {resp.status}: {raw_body}")
                return resp
        except (aiohttp.ClientConnectionError, aiohttp.ServerDisconnectedError, aiohttp.ClientPayloadError):
            print("Lost connection!")
            raise McpConnectionError("Lost connection to MCP server")
    
    def _handle_json_response(self, raw_body: dict) -> dict:
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            raise RuntimeError(f"Returned non-JSON: {raw_body}")
        if "error" in data:
            raise RuntimeError(f"Initialize error: {data['error']}")
        return data
    
    def _handle_sse_response(self, raw_body: str) -> dict:
        events = []
        for line in raw_body.splitlines():
            if line.startswith("data:"):
                json_str = line[len("data:"):].strip()
                try:
                    events.append(json.loads(json_str))
                except json.JSONDecodeError:
                    events.append(json_str)  # keep raw if JSON fails
        return events

    async def _parse_response(self, ctype: str, response: ClientResponse) -> dict:
        raw_body = await response.text()
        if ctype == "application/json":
            return self._handle_json_response(raw_body)
        elif ctype == "text/event-stream":
            return self._handle_sse_response(raw_body)
        else:
            raise RuntimeError(f"Unexpected Content-Type: {ctype}, body: {raw_body}")
    