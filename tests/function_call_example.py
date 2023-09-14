import json


def get_current_weather(location, unit="fahrenheit"):
    """Get the current weather in a given location"""
    weather_info = {
        "location": location,
        "temperature": "72",
        "unit": unit,
        "forecast": ["sunny", "windy"],
    }
    return json.dumps(weather_info)


functions = [
    {
        "name": "get_current_weather",
        "description": "Get the current weather in a given location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA",
                },
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["location"],
        },
    }
]


def before_get_current_weather(*, messages):
    print("before_get_current_weather called")


def after_get_current_weather(*, function_response, messages):
    print("after_get_current_weather called")


function_callbacks = [
    {
        "function_name": "get_current_weather",
        "callback_type": "before",
        "callback_function_name": "before_get_current_weather",
        # parameters: messages
    },
    {
        "function_name": "get_current_weather",
        "callback_type": "after",
        "callback_function_name": "after_get_current_weather",
        # parameters: function_response, messages
    },
]
