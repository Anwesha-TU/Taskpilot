from typing import Callable, Dict


class ToolRegistry:

    def __init__(self):
        self._tools: Dict[str, Dict] = {}

    def register(self, name: str, description: str):

        def decorator(function: Callable):

            self._tools[name] = {
                "function": function,
                "description": description
            }

            return function

        return decorator

    def get(self, name: str) -> Callable:

        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")

        return self._tools[name]["function"]

    def execute(self, name: str, **kwargs):

        function = self.get(name)

        return function(**kwargs)

    def list_tools(self):

        return {
            name: data["description"]
            for name, data in self._tools.items()
        }


# Global tool registry
registry = ToolRegistry()
