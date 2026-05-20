import json
import logging
from typing import List, Dict, Any
from openai import AsyncAzureOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.inventory import Product, Inventory
from app.ml.demand_forecast import demand_forecast_engine
from app.ml.vendor_ranker import vendor_ranker_engine

logger = logging.getLogger("app.services.copilot_agent")

# Initialize the Azure OpenAI Async Client
aclient = AsyncAzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    api_version=settings.AZURE_OPENAI_API_VERSION,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
)

class CopilotOrchestrator:
    """Agentic Orchestrator mapping natural language to strict database/ML outputs."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        
        # Define the strict tools the LLM can trigger (No manual calculations allowed)
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_stockout_risks",
                    "description": "Fetch a list of products currently at risk of stockout based on predictive demand.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_return_insights",
                    "description": "Analyze why returns are happening for a specific product category.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "description": "The product category, e.g., 'Monitors'"}
                        },
                        "required": ["category"]
                    }
                }
            }
        ]

    async def _execute_tool(self, function_name: str, arguments: dict) -> str:
        """Executes the mapped backend function to fetch hard data metrics."""
        if function_name == "get_stockout_risks":
            # Direct DB Query + ML execution
            result = await self.db.execute(select(Product, Inventory).join(Inventory))
            items = result.all()
            
            risks = []
            for product, inv in items[:5]: # Limit for context size
                if inv.current_stock <= inv.reorder_point:
                    risks.append({
                        "product": product.product_name,
                        "current_stock": inv.current_stock,
                        "abc_class": product.abc_class
                    })
            return json.dumps({"status": "success", "data": risks if risks else "No immediate stockout risks detected."})
            
        elif function_name == "get_return_insights":
            category = arguments.get("category", "General")
            # Mocking DB extraction for demonstration
            data = {
                "category": category,
                "average_return_rate": "12.5%",
                "top_reasons": ["Logistics Damage (45%)", "Defective Component (30%)", "Fraud Risk (15%)"]
            }
            return json.dumps({"status": "success", "data": data})
            
        return json.dumps({"status": "error", "message": "Unknown analytical tool requested."})

    async def process_chat(self, user_prompt: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Runs the LLM loop: Intent recognition -> Tool Execution -> Semantic Explanation."""
        
        system_prompt = {
            "role": "system",
            "content": (
                "You are the AI Inventory Copilot, an enterprise-grade supply chain assistant. "
                "You MUST NOT perform mathematical calculations yourself. If the user asks for metrics, "
                "call the appropriate function to get hard data from the database, then explain that data "
                "in a professional, business-friendly manner. Format responses with markdown for readability."
            )
        }
        
        messages = [system_prompt] + history + [{"role": "user", "content": user_prompt}]
        
        try:
            # Step 1: Send prompt to LLM to evaluate if a tool call is needed
            response = await aclient.chat.completions.create(
                model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=messages,
                tools=self.tools,
                tool_choice="auto"
            )
            
            response_message = response.choices[0].message
            executed_tools = []
            
            # Step 2: Intercept Tool Calls (Function execution)
            if response_message.tool_calls:
                messages.append(response_message) # Append assistant's tool call request
                
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"LLM triggered tool: {function_name} with args {arguments}")
                    executed_tools.append(function_name)
                    
                    # Execute backend data extraction
                    function_response = await self._execute_tool(function_name, arguments)
                    
                    # Append hard data back to the conversation
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response,
                    })
                
                # Step 3: Get final semantic explanation from LLM using the hard data
                final_response = await aclient.chat.completions.create(
                    model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                    messages=messages
                )
                
                return {
                    "generated_reply": final_response.choices[0].message.content,
                    "executed_tools": executed_tools
                }
            
            # If no tools were needed, return standard reply
            return {
                "generated_reply": response_message.content,
                "executed_tools": []
            }
            
        except Exception as e:
            logger.error(f"Azure OpenAI Integration Error: {str(e)}", exc_info=True)
            return {
                "generated_reply": "I am currently unable to reach the AI reasoning engine due to a systemic timeout. Please verify API configurations.",
                "executed_tools": []
            }