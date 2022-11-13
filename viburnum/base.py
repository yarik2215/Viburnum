from typing import Callable
import weakref


# __________________ Resource Connector ___________________


class ResourceConnector:
    def __init__(
        self,
        handler: "Handler",
        resource_name: str,
    ) -> None:
        handler.resources.add(self)
        self.handler = weakref.proxy(handler)
        self.resource_name = resource_name
        self._client = None

    def get_resource_client(self):
        """Return resource client or None"""
        return None


# ___________________ Handler ____________________________


class LambdaInput:
    def __init__(self, event: dict, context: dict) -> None:
        self.event = event
        # TODO: context is not dict type
        self.context = context


class LambdaOutput:
    def as_response(self) -> dict:
        return {}


class Handler:
    event_class = LambdaInput

    def __init__(
        self,
        func: Callable,
    ) -> None:
        self.name = f"{func.__name__}{self._name_suffix()}"
        self.func = func
        self.resources: set[ResourceConnector] = set()
        self.extra_kwargs: dict = {}  # DEPRECATED: useless

    def __call__(self, event: dict, context: dict) -> dict:

        response = self.func(
            self.event_class(event, context), **self._get_resource_clients()
        )
        if isinstance(response, LambdaOutput):
            return response.as_response()
        response

    def _get_resource_clients(self) -> dict:
        return {r.resource_name: r.get_resource_client() for r in self.resources}

    @staticmethod
    def _name_suffix() -> str:
        """
        Return suffix that will be added to function name
        for creating name for lambda.
        """
        return ""


# __________________________ Resource _____________________________


class Resource:
    def __init__(self, name: str) -> None:
        self.name = name


# __________________________ Application ___________________________


class Application:
    def __init__(self, name: str) -> None:
        self.name: str = name
        self.handlers: list[Handler] = []
        self.resources: dict[str, Resource] = {}

    def add_handler(self, handler: Handler) -> None:
        self.handlers.append(handler)

    def add_resource(self, resource: Resource) -> None:
        self.resources[resource.name] = resource
