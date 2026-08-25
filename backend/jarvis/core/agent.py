from ollama import ResponseError
from jarvis.core.llm import LLMClient
from jarvis.core.tools import AVAILABLE_TOOLS

SYSTEM_PROMPT = """You are Jarvis, a fast local desktop assistant.

Your priorities:
1. Be concise and conversational.
2. Use tools when the user's request requires a desktop action.
3. Never claim an action was completed unless the tool result confirms it.
4. Do not explain your internal reasoning.
5. For simple commands, respond briefly.

Available tools let you open applications, open URLs, and get the current date/time.
"""

class JarvisAgent:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.enabled = True
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def run(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})

        # Give the model the callable functions directly. Ollama's Python
        # client converts their signatures/docstrings into tool schemas.
        response = self.llm.chat(
            messages=self.messages,
            tools=list(AVAILABLE_TOOLS.values()),
        )
        self.messages.append(response.message)

        if response.message.tool_calls:
            for call in response.message.tool_calls:
                name = call.function.name
                args = dict(call.function.arguments)
                function = AVAILABLE_TOOLS.get(name)

                if function is None:
                    result = f"Unknown tool: {name}"
                else:
                    try:
                        result = str(function(**args))
                    except Exception as exc:
                        result = f"Tool execution failed: {exc}"

                self.messages.append({
                    "role": "tool",
                    "tool_name": name,
                    "content": result,
                })

            final = self.llm.chat(
                messages=self.messages,
                tools=list(AVAILABLE_TOOLS.values()),
            )
            self.messages.append(final.message)
            return final.message.content or "Done."

        return response.message.content or "I'm ready."

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled
