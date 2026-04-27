import asyncio
import os
import time
from contextlib import AsyncExitStack
from typing import Any

from google import genai
from google.genai import types
from client import MCPClient
from dotenv import load_dotenv

load_dotenv()


class ChatHost:
    def __init__(self):
        self.mcp_clients: list[MCPClient] = [MCPClient("./weather_USA.py"), MCPClient("./weather_Israel.py"), MCPClient("./rag_tool.py")]
        self.tool_clients: dict[str, tuple[MCPClient, str]] = {}
        self.clients_connected = False
        self.exit_stack = AsyncExitStack()
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    async def connect_mcp_clients(self):
        """Connect all configured MCP clients once."""
        if self.clients_connected:
            return

        for client in self.mcp_clients:
            if client.session is None:
                await client.connect_to_server()

        if not self.mcp_clients:
            raise RuntimeError("No MCP clients are connected")

        self.clients_connected = True

    async def get_available_tools(self) -> list[dict[str, Any]]:
        """Collect tools from all MCP clients and map them back to their owner."""
        await self.connect_mcp_clients()
        self.tool_clients = {}
        available_tools: list[dict[str, Any]] = []

        for client in self.mcp_clients:
            if client.session is None:
                print(f"Warning: MCP client {client.client_name} is not connected, skipping")
                continue

            try:
                response = await client.session.list_tools()
                for tool in response.tools:
                    exposed_name = f"{client.client_name}_{tool.name}"
                    if exposed_name in self.tool_clients:
                        raise RuntimeError(f"Duplicate tool name detected: {exposed_name}")

                    self.tool_clients[exposed_name] = (client, tool.name)
                    available_tools.append(
                        {
                            "name": exposed_name,
                            "description": f"[{client.client_name}] {tool.description}",
                            "input_schema": tool.inputSchema,
                        }
                    )
            except Exception as e:
                print(f"Warning: Failed to get tools from {client.client_name}: {str(e)}")
                continue

        if not available_tools:
            raise RuntimeError("No tools available from any MCP client")

        return available_tools


    def _clean_schema(self, schema: dict) -> dict:
        """Recursively remove unsupported fields from JSON schema."""
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            self._clean_schema(prop)
        return schema

    def _build_gemini_tools(self, available_tools: list[dict[str, Any]]) -> list:
        """Convert MCP tool schemas to Gemini function declarations."""
        declarations = []
        for t in available_tools:
            schema = self._clean_schema(t["input_schema"].copy())
            declarations.append(
                types.Tool(function_declarations=[
                    types.FunctionDeclaration(
                        name=t["name"],
                        description=t["description"],
                        parameters=schema,
                    )
                ])
            )
        return declarations

    def _generate(self, contents, config, retries=3):
        for attempt in range(retries):
            try:
                return self.client.models.generate_content(model=os.environ["GEMINI_MODEL"], contents=contents, config=config)
            except Exception as e:
                err = str(e)
                if attempt < retries - 1 and ("503" in err or "429" in err):
                    import re
                    match = re.search(r"retryDelay.*?(\d+)s", err)
                    wait = int(match.group(1)) + 1 if match else 5 * (attempt + 1)
                    print(f"Rate limited, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise

    async def process_query(self, query: str) -> str:
        """Process a query using Gemini and available tools"""
        available_tools = await self.get_available_tools()
        gemini_tools = self._build_gemini_tools(available_tools)
        history = [types.Content(role="user", parts=[types.Part(text=query)])]
        final_text = []

        config = types.GenerateContentConfig(
            tools=gemini_tools,
            system_instruction=(
                "You are a helpful assistant. "
                "When asked about weather in Israel, immediately call open_weather_forecast_israel, "
                "then enter_weather_forecast_city_israel with the city name, "
                "then select_weather_forecast_city_israel, "
                "then get_weather_forecast_israel to read the result. "
                "When the user asks a question about the content of a web page or provides a URL, "
                "call fetch_page_content with that URL and answer directly from the returned text. "
                "Do NOT ask for confirmation. Just call the tools in order."
            ),
        )

        response = self._generate(history, config)

        while True:
            tool_parts = []
            saw_tool_use = False
            history.append(response.candidates[0].content)

            for part in response.candidates[0].content.parts:
                if part.text:
                    final_text.append(part.text)
                elif part.function_call:
                    saw_tool_use = True
                    tool_name = part.function_call.name
                    tool_args = dict(part.function_call.args)

                    if tool_name not in self.tool_clients:
                        raise RuntimeError(f"Unknown tool requested by model: {tool_name}")

                    client, original_tool_name = self.tool_clients[tool_name]
                    result = await client.session.call_tool(original_tool_name, tool_args)
                    final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
                    result_text = "".join(c.text for c in result.content if hasattr(c, "text"))
                    tool_parts.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"result": result_text},
                        )
                    )

            if not saw_tool_use:
                break

            history.append(types.Content(role="user", parts=tool_parts))
            response = self._generate(history, config)

        return "\n".join(final_text)
    
    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                
                if query.lower() == 'quit':
                    break
                
                response = await self.process_query(query)
                print("\n" + response)
                
            except Exception as e:
                print(f"\nchat_loop Error: {str(e)}")
                
    async def cleanup(self):
        """Clean up resources"""
        for client in reversed(self.mcp_clients):
            await client.cleanup()
        await self.exit_stack.aclose()
        
        
async def main():
    host = ChatHost()
    try:
        await host.chat_loop()
    finally:
        await host.cleanup()
        
if __name__ == "__main__":
    asyncio.run(main())
