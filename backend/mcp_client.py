"""
JARVIS MCP Client Daemon
Connects to any MCP server via stdio/SSE/HTTP, discovers tools,
routes actions through the MCP protocol, and logs every invocation
to the compliance ledger.

This is the Context Matrix — the moat that makes JARVIS the
enterprise execution layer.
"""
import asyncio
import json
import time
import logging
import os
import hashlib
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum

log = logging.getLogger("jarvis-mcp")


class TransportType(str, Enum):
    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable-http"


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server connection."""
    name: str
    transport: TransportType
    # stdio transport
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None
    # HTTP/SSE transport
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    # Auth
    auth_token: Optional[str] = None
    auth_header: str = "Authorization"
    # Metadata
    description: str = ""
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    priority: int = 0  # Higher = tried first


@dataclass
class MCPTool:
    """Discovered tool from an MCP server."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_name: str
    output_schema: Optional[Dict[str, Any]] = None


@dataclass
class MCPResource:
    """Discovered resource from an MCP server."""
    uri: str
    name: str
    description: str
    mime_type: str
    server_name: str


@dataclass
class MCPToolResult:
    """Result of a tool invocation."""
    content: List[Dict[str, Any]]
    structured_content: Optional[Dict[str, Any]] = None
    is_error: bool = False
    server_name: str = ""
    tool_name: str = ""
    duration_ms: float = 0


class JARVISMCPClient:
    """
    The JARVIS MCP Client Daemon.
    
    Manages connections to multiple MCP servers, discovers their
    tools/resources/prompts, and routes actions through them.
    Every invocation is logged to the compliance ledger.
    """

    def __init__(self):
        self.servers: Dict[str, MCPServerConfig] = {}
        self._sessions: Dict[str, Any] = {}  # server_name -> active session
        self._tools: Dict[str, MCPTool] = {}  # tool_name -> MCPTool
        self._tool_to_server: Dict[str, str] = {}  # tool_name -> server_name
        self._resources: Dict[str, MCPResource] = {}
        self._connected: Dict[str, bool] = {}
        self._ledger: Optional["ComplianceLedger"] = None

    def set_ledger(self, ledger: "ComplianceLedger"):
        self._ledger = ledger

    def register_server(self, config: MCPServerConfig):
        """Register an MCP server for connection."""
        self.servers[config.name] = config
        log.info(f"Registered MCP server: {config.name} ({config.transport.value})")

    def load_config(self, config_path: str):
        """Load MCP server configurations from a JSON file."""
        if not os.path.exists(config_path):
            log.warning(f"MCP config not found: {config_path}")
            return

        with open(config_path, "r") as f:
            data = json.load(f)

        for name, server_cfg in data.get("mcpServers", {}).items():
            transport = TransportType(server_cfg.get("transport", "stdio"))
            config = MCPServerConfig(
                name=name,
                transport=transport,
                command=server_cfg.get("command"),
                args=server_cfg.get("args", []),
                env=server_cfg.get("env"),
                cwd=server_cfg.get("cwd"),
                url=server_cfg.get("url"),
                headers=server_cfg.get("headers"),
                auth_token=server_cfg.get("authToken"),
                description=server_cfg.get("description", ""),
                tags=server_cfg.get("tags", []),
                enabled=server_cfg.get("enabled", True),
                priority=server_cfg.get("priority", 0),
            )
            if config.enabled:
                self.register_server(config)

    async def connect_all(self):
        """Connect to all registered MCP servers."""
        tasks = []
        for name, config in sorted(
            self.servers.items(),
            key=lambda x: x[1].priority,
            reverse=True,
        ):
            tasks.append(self._connect_server(name, config))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, result in zip(self.servers.keys(), results):
            if isinstance(result, Exception):
                log.error(f"Failed to connect to {name}: {result}")
                self._connected[name] = False
            else:
                self._connected[name] = True

    async def _connect_server(self, name: str, config: MCPServerConfig):
        """Connect to a single MCP server and discover its tools."""
        log.info(f"Connecting to MCP server: {name}...")

        try:
            if config.transport == TransportType.STDIO:
                await self._connect_stdio(name, config)
            elif config.transport in (TransportType.SSE, TransportType.STREAMABLE_HTTP):
                await self._connect_http(name, config)
        except Exception as e:
            log.error(f"Connection failed for {name}: {e}")
            raise

    async def _connect_stdio(self, name: str, config: MCPServerConfig):
        """Connect via stdio transport (subprocess)."""
        try:
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client, StdioServerParameters
        except ImportError:
            log.warning("mcp package not installed — using built-in JSON-RPC client")
            await self._connect_stdio_fallback(name, config)
            return

        server_params = StdioServerParameters(
            command=config.command,
            args=config.args or [],
            env=config.env,
            cwd=config.cwd,
        )

        read_stream, write_stream = await stdio_client(server_params).__aenter__()
        session = ClientSession(read_stream, write_stream)
        await session.__aenter__()
        await session.initialize()

        self._sessions[name] = session
        await self._discover_tools(name, session)
        log.info(f"Connected to {name} via stdio")

    async def _connect_stdio_fallback(self, name: str, config: MCPServerConfig):
        """Built-in stdio client when mcp package is not installed."""
        proc = await asyncio.create_subprocess_exec(
            config.command, *(config.args or []),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, **(config.env or {})} if config.env else None,
            cwd=config.cwd,
        )

        # Send initialize
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"roots": {"listChanged": True}},
                "clientInfo": {"name": "JARVIS", "version": "3.0.0"},
            },
        }
        await self._send_stdio(proc, init_msg)
        resp = await self._recv_stdio(proc)

        # Send initialized notification
        await self._send_stdio(proc, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })

        self._sessions[name] = {"proc": proc, "next_id": 10}
        await self._discover_tools_builtin(name, proc)
        log.info(f"Connected to {name} via stdio (builtin client)")

    async def _connect_http(self, name: str, config: MCPServerConfig):
        """Connect via HTTP transport (SSE or Streamable HTTP)."""
        import aiohttp

        headers = {"Content-Type": "application/json"}
        if config.headers:
            headers.update(config.headers)
        if config.auth_token:
            headers[config.auth_header] = f"Bearer {config.auth_token}"

        session = aiohttp.ClientSession(headers=headers)
        self._sessions[name] = {"session": session, "url": config.url, "next_id": 1}

        # Initialize
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"roots": {"listChanged": True}},
                "clientInfo": {"name": "JARVIS", "version": "3.0.0"},
            },
        }

        async with session.post(config.url, json=init_msg) as resp:
            if resp.status == 200:
                data = await resp.json()
                log.info(f"Connected to {name} via HTTP: {data.get('result', {}).get('serverInfo', {})}")

        # Send initialized
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        async with session.post(config.url, json=notif):
            pass

        await self._discover_tools_http(name, session, config.url)

    async def _discover_tools(self, name: str, session):
        """Discover tools from an MCP session (official SDK)."""
        try:
            tools_resp = await session.list_tools()
            for tool in tools_resp.tools:
                mcp_tool = MCPTool(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.inputSchema if hasattr(tool, "inputSchema") else {},
                    server_name=name,
                )
                self._tools[tool.name] = mcp_tool
                self._tool_to_server[tool.name] = name
            log.info(f"Discovered {len(tools_resp.tools)} tools from {name}")
        except Exception as e:
            log.error(f"Tool discovery failed for {name}: {e}")

    async def _discover_tools_builtin(self, name: str, proc):
        """Discover tools using built-in JSON-RPC client."""
        msg = {"jsonrpc": "2.0", "id": 100, "method": "tools/list"}
        await self._send_stdio(proc, msg)
        resp = await self._recv_stdio(proc)

        if resp and "result" in resp:
            for tool in resp["result"].get("tools", []):
                mcp_tool = MCPTool(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    input_schema=tool.get("inputSchema", {}),
                    server_name=name,
                )
                self._tools[tool["name"]] = mcp_tool
                self._tool_to_server[tool["name"]] = name
            log.info(f"Discovered {len(resp['result'].get('tools', []))} tools from {name}")

    async def _discover_tools_http(self, name: str, session, url):
        """Discover tools via HTTP transport."""
        msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        async with session.post(url, json=msg) as resp:
            if resp.status == 200:
                data = await resp.json()
                for tool in data.get("result", {}).get("tools", []):
                    mcp_tool = MCPTool(
                        name=tool["name"],
                        description=tool.get("description", ""),
                        input_schema=tool.get("inputSchema", {}),
                        server_name=name,
                    )
                    self._tools[tool["name"]] = mcp_tool
                    self._tool_to_server[tool["name"]] = name
                log.info(f"Discovered {len(data.get('result', {}).get('tools', []))} tools from {name}")

    def get_tools(self) -> List[MCPTool]:
        """Return all discovered tools."""
        return list(self._tools.values())

    def get_tool(self, name: str) -> Optional[MCPTool]:
        return self._tools.get(name)

    def get_tools_for_server(self, server_name: str) -> List[MCPTool]:
        return [t for t in self._tools.values() if t.server_name == server_name]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPToolResult:
        """
        Invoke an MCP tool. Routes to the correct server.
        Logs the invocation to the compliance ledger.
        """
        if tool_name not in self._tools:
            return MCPToolResult(
                content=[{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                is_error=True,
                tool_name=tool_name,
            )

        tool = self._tools[tool_name]
        server_name = self._tool_to_server[tool_name]
        start = time.time()

        try:
            if server_name in self._sessions:
                session = self._sessions[server_name]
                result = await self._invoke_tool(server_name, session, tool_name, arguments)
            else:
                result = MCPToolResult(
                    content=[{"type": "text", "text": f"Server {server_name} not connected"}],
                    is_error=True,
                    tool_name=tool_name,
                    server_name=server_name,
                )
        except Exception as e:
            result = MCPToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                is_error=True,
                tool_name=tool_name,
                server_name=server_name,
            )

        result.duration_ms = (time.time() - start) * 1000

        # Log to compliance ledger
        if self._ledger:
            await self._ledger.log_invocation(
                tool_name=tool_name,
                server_name=server_name,
                arguments=arguments,
                result=asdict(result),
                duration_ms=result.duration_ms,
                is_error=result.is_error,
            )

        log.info(
            f"Tool {tool_name} on {server_name}: "
            f"{'ERROR' if result.is_error else 'OK'} "
            f"({result.duration_ms:.0f}ms)"
        )
        return result

    async def _invoke_tool(
        self, server_name: str, session, tool_name: str, arguments: Dict[str, Any]
    ) -> MCPToolResult:
        """Route tool invocation to the correct transport."""
        # Official SDK session
        if hasattr(session, "call_tool"):
            resp = await session.call_tool(tool_name, arguments)
            return MCPToolResult(
                content=[asdict(c) for c in resp.content] if hasattr(resp, "content") else [],
                structured_content=getattr(resp, "structuredContent", None),
                is_error=getattr(resp, "isError", False),
                server_name=server_name,
                tool_name=tool_name,
            )

        # Built-in stdio client
        if "proc" in session:
            msg_id = session.get("next_id", 10)
            session["next_id"] = msg_id + 1
            msg = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }
            await self._send_stdio(session["proc"], msg)
            resp = await self._recv_stdio(session["proc"])

            if resp and "result" in resp:
                return MCPToolResult(
                    content=resp["result"].get("content", []),
                    is_error=resp["result"].get("isError", False),
                    server_name=server_name,
                    tool_name=tool_name,
                )
            elif resp and "error" in resp:
                return MCPToolResult(
                    content=[{"type": "text", "text": resp["error"].get("message", "Unknown error")}],
                    is_error=True,
                    server_name=server_name,
                    tool_name=tool_name,
                )

        # HTTP client
        if "session" in session and "url" in session:
            http_session = session["session"]
            msg_id = session.get("next_id", 10)
            session["next_id"] = msg_id + 1
            msg = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }
            async with http_session.post(session["url"], json=msg) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "result" in data:
                        return MCPToolResult(
                            content=data["result"].get("content", []),
                            is_error=data["result"].get("isError", False),
                            server_name=server_name,
                            tool_name=tool_name,
                        )

        return MCPToolResult(
            content=[{"type": "text", "text": "No compatible session found"}],
            is_error=True,
            server_name=server_name,
            tool_name=tool_name,
        )

    async def _send_stdio(self, proc, msg: dict):
        """Send a JSON-RPC message via stdio."""
        data = json.dumps(msg) + "\n"
        proc.stdin.write(data.encode())
        await proc.stdin.drain()

    async def _recv_stdio(self, proc, timeout: float = 30) -> Optional[dict]:
        """Receive a JSON-RPC response from stdio."""
        try:
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
            if line:
                return json.loads(line.decode().strip())
        except asyncio.TimeoutError:
            log.warning("Stdio response timed out")
        except json.JSONDecodeError as e:
            log.warning(f"Invalid JSON from stdio: {e}")
        return None

    async def disconnect_all(self):
        """Disconnect from all MCP servers."""
        for name, session in self._sessions.items():
            try:
                if hasattr(session, "__aexit__"):
                    await session.__aexit__(None, None, None)
                elif "proc" in session:
                    session["proc"].terminate()
                elif "session" in session:
                    await session["session"].close()
            except Exception as e:
                log.warning(f"Error disconnecting {name}: {e}")
        self._sessions.clear()
        self._tools.clear()
        self._tool_to_server.clear()
        self._resources.clear()
        self._connected.clear()

    def get_status(self) -> Dict[str, Any]:
        """Return status of all MCP connections."""
        return {
            "servers": {
                name: {
                    "connected": self._connected.get(name, False),
                    "transport": config.transport.value,
                    "tools": len(self.get_tools_for_server(name)),
                    "description": config.description,
                }
                for name, config in self.servers.items()
            },
            "total_tools": len(self._tools),
            "total_servers": len(self.servers),
            "connected_servers": sum(1 for v in self._connected.values() if v),
        }


# ── Singleton ────────────────────────────────────────────────────────────
_client: Optional[JARVISMCPClient] = None


def get_mcp_client() -> JARVISMCPClient:
    global _client
    if _client is None:
        _client = JARVISMCPClient()
    return _client
