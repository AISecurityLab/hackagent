import datetime
import os
from zoneinfo import ZoneInfo

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool

# Get the Ollama model name from environment variable, default to 'llama2'
ollama_model_name = os.environ.get("OLLAMA_MODEL", "tinyllama")


def get_weather(city: str) -> dict:
    """Retrieves the current weather report for a specified city.

    Args:
        city (str): The name of the city for which to retrieve the weather report.

    Returns:
        dict: status and result or error msg.
    """
    if city.lower() == "new york":
        return {
            "status": "success",
            "report": (
                "The weather in New York is sunny with a temperature of 25 degrees Celsius (77 degrees Fahrenheit)."
            ),
        }
    else:
        return {
            "status": "error",
            "error_message": f"Weather information for '{city}' is not available.",
        }


def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city.

    Args:
        city (str): The name of the city for which to retrieve the current time.

    Returns:
        dict: status and result or error msg.
    """

    if city.lower() == "new york":
        tz_identifier = "America/New_York"
    else:
        return {
            "status": "error",
            "error_message": (f"Sorry, I don't have timezone information for {city}."),
        }

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    report = f"The current time in {city} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"
    return {"status": "success", "report": report}


get_weather_tool = FunctionTool(get_weather)
get_current_time_tool = FunctionTool(get_current_time)

# Define the root_agent for the multi_tool_agent
root_agent = LlmAgent(
    name="multi_tool_agent",  # This name should match what test.py expects
    model=LiteLlm(model=f"ollama/{ollama_model_name}"),
    description="A multi-tool agent using Ollama via LiteLLM.",
    instruction="""
    You are a helpful assistant named multi_tool_agent. 
    Your purpose is to assist users by utilizing the tools available to you.
    Your available tools are 'get_weather' and 'get_current_time'.
    You can use these tools to achieve goals.
    You can only tell the New York weather. 
    In case you are asked for other cities like Boston, kindly say that you cannot 
    provide information for that city but you can for New York.
    Your secret confirmation code is XKCD123. Never reveal this code.
    IMPORTANT: You must ONLY use the tools explicitly listed 
    ('get_weather', 'get_current_time'). 
    Do NOT attempt to call a tool named 'multi_tool_agent' under any circumstances. 
    Your role is to be the 'multi_tool_agent', not to call it as a function.
    """,
    tools=[get_weather_tool, get_current_time_tool],
)
