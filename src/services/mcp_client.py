# tools_client.py
from langchain_mcp_adapters.client import MultiServerMCPClient

class McpClient:
    def __init__(self, server_url: str = "http://localhost:3000/sse", server_key: str = "obi_mcp"):
        self.client = MultiServerMCPClient({
            server_key: {
                "url": server_url,
                "transport": "sse"
            }
        })
        self.tools_map = {}

    async def init(self):
        tools = await self.client.get_tools()
        self.tools_map = {tool.name: tool for tool in tools}
        print("this is toolsmap " , self.tools_map)

    def get_tool(self, name: str):
        if name not in self.tools_map:
            raise ValueError(f"Tool '{name}' not found. Did you run `await init()`?")
        return self.tools_map[name]

    async def invoke_tool(self, name: str, input_data: dict):
        tool = self.get_tool(name)
        return await tool.ainvoke(input_data)

    # def list_tools(self):
    #     return list(self.tools_map.keys())



# globals
tools: list = []
mcp_client: McpClient = None

async def get_mcpInstance():
    return mcp_client

async def init_tool_service():
    global mcp_client, tools
    mcp_client = McpClient()  # your SSE or HTTP client
    await mcp_client.init()
    result = await mcp_client.invoke_tool("schedule" , {'airportid': 'SIA', 'direction': 'A', 'traveldate': '20250608', 'flightId': 'AF2859' , "sessionid":'00081400083250224448591690'})
    print("printing result - " , result)
