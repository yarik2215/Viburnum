import inspect
import logging
import os
import shutil
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

import pip
from aws_cdk import (
    Duration,
    Stack,
    aws_apigateway,
    aws_events,
    aws_events_targets,
    aws_lambda,
    aws_lambda_event_sources,
    aws_sqs,
)
from constructs import Construct

from viburnum.application import (
    Application,
    Handler,
    Resource,
    ResourceConnector,
    Sqs,
    SqsPermission,
)
from viburnum.application.connectors import SqsConnector
from viburnum.application.handlers import ApiHandler, JobHandler, SqsHandler


def get_builder_class(primitive):
    return getattr(sys.modules[__name__], f"{primitive.__class__.__name__}Builder")


class AppConstruct(Stack):
    def __init__(self, scope: Construct, app: Application, **kwargs) -> None:
        super().__init__(scope, app.name, **kwargs)

        self._app = app
        self._built_resources = {}

        self._prepare_shared_layer()
        self._prepare_libraries_layer()
        self._build_shared_layer()
        self._build_lib_layer()

        self._build_resources()
        self._build_handlers()

    def _build_resources(self):
        for resource in self._app.resources.values():
            builder_class = getattr(
                sys.modules[__name__], f"{resource.__class__.__name__}Builder"
            )
            # FIXME: raise error if there were resources with identical names
            self._built_resources[resource.name] = builder_class(self, resource).build()

    def _build_handlers(self):
        for handler in self._app.handlers:
            handler_class = getattr(
                sys.modules[__name__], f"{handler.__class__.__name__}Builder"
            )
            handler_class(self, handler).build()

    def _prepare_shared_layer(self):
        logging.info("Preparing shared layer")
        shared_layer_folder = Path("./.layers/shared")
        if os.path.exists(shared_layer_folder):
            shutil.rmtree(shared_layer_folder)
        os.mkdir(shared_layer_folder)
        shutil.copytree("shared", str(shared_layer_folder.joinpath("python/shared")))

    def _prepare_libraries_layer(self):
        logging.info("Preparing libraries layer")
        lib_layer_folder = Path("./.layers/lib")
        if os.path.exists(lib_layer_folder):
            shutil.rmtree(lib_layer_folder)
        os.mkdir(lib_layer_folder)
        shutil.copy("requirements.txt", str(lib_layer_folder))

        # TODO: use docker container for building lib layer
        pip.main(
            [
                "install",
                "-r",
                "requirements.txt",
                "--target",
                str(lib_layer_folder.joinpath("python")),
            ]
        )

    def _build_shared_layer(self):
        self._shared_layer = aws_lambda.LayerVersion(
            self,
            "SharedLayer",
            code=aws_lambda.Code.from_asset(
                str(Path("./.layers/shared")),
            ),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_9],
        )

    def _build_lib_layer(self):
        self._lib_layer = aws_lambda.LayerVersion(
            self,
            "LibLayer",
            code=aws_lambda.Code.from_asset(
                str(Path("./.layers/lib")),
            ),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_9],
        )

    def _build_sqs(self, sqs: Sqs):
        queue = aws_sqs.Queue(
            self, sqs.name, visibility_timeout=Duration.seconds(sqs.visibility_timeout)
        )
        self._built_resources[sqs.name] = queue
        return queue

    def get_built_resource(self, name: str):
        return self._built_resources[name]


# ______________ Handler Builders __________________ #


HandlerType = TypeVar("HandlerType", bound=Handler)


class HandlerBuilder(Generic[HandlerType]):
    def __init__(self, context: "AppConstruct", handler: HandlerType) -> None:
        self.context = context
        self.handler = handler

    def _build_lambda(self):
        dir_ = Path(inspect.getfile(self.handler.func)).parent

        # TODO: add more config options
        lambda_fn = aws_lambda.Function(
            self.context,
            self.handler.name,
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            handler=f"handler.{self.handler.func.__name__}",
            code=aws_lambda.Code.from_asset(str(dir_)),
            environment={
                "APP_NAME": self.context._app.name,
                # "AWS_REGION": self.context.region, This variable is reserved
            },
            layers=[self.context._shared_layer, self.context._lib_layer],
        )
        return lambda_fn

    def _connect_resources(self, lambda_: aws_lambda.Function):
        # FIXME: very bad pattern
        for connector in self.handler.resources:
            get_builder_class(connector)(self.context, connector, lambda_).build()

    def build(self):
        # TODO: rework inheritance
        lambda_ = self._build_lambda()
        self._connect_resources(lambda_)
        return lambda_


class ApiHandlerBuilder(HandlerBuilder[ApiHandler]):
    _api = None

    @property
    def api(self) -> aws_apigateway.RestApi:
        if not self.__class__._api:
            self.__class__._api = aws_apigateway.RestApi(
                self.context, f"{self.context._app.name}Api"
            )
        return self.__class__._api

    def build(self):
        lambda_ = super().build()
        self._build_endpoint(lambda_)
        return lambda_

    def _build_endpoint(self, lambda_: aws_lambda.Function):
        integration = aws_apigateway.LambdaIntegration(lambda_)

        endpoint = self.api.root
        for path_part in (p for p in self.handler.path.split("/") if p):
            endpoint = endpoint.get_resource(path_part) or endpoint.add_resource(
                path_part
            )
        for method in self.handler.methods:
            endpoint.add_method(method, integration)


class JobHandlerBuilder(HandlerBuilder[JobHandler]):
    def build(self):
        lambda_ = super().build()
        self._build_rule(lambda_)
        return lambda_

    def _build_rule(self, lambda_):
        aws_events.Rule(
            self.context,
            f"{self.handler.name}_rule",
            schedule=aws_events.Schedule.expression(self.handler.schedule),
            targets=[aws_events_targets.LambdaFunction(lambda_)],
        )


class SqsHandlerBuilder(HandlerBuilder[SqsHandler]):
    def build(self):
        lambda_ = super().build()
        self._handler_connect_queue(lambda_)
        return lambda_

    def _handler_connect_queue(self, lambda_: aws_lambda.Function):
        queue: aws_sqs.Queue = self.context.get_built_resource(self.handler.queue_name)
        # TODO: add more config options including enabling report_batch_item_failure
        _sqs_event_source = aws_lambda_event_sources.SqsEventSource(queue)
        lambda_.add_event_source(_sqs_event_source)


# ______________ Resource Builders __________________ #


ResourceType = TypeVar("ResourceType", bound=Resource)


class ResourceBuilder(ABC, Generic[ResourceType]):
    def __init__(self, context: "AppConstruct", resource: ResourceType) -> None:
        self.context = context
        self.resource = resource

    @abstractmethod
    def build(self):
        ...


class SqsBuilder(ResourceBuilder[Sqs]):
    def build(self):
        # TODO: add more config options
        queue = aws_sqs.Queue(
            self.context,
            self.resource.name,
            visibility_timeout=Duration.seconds(self.resource.visibility_timeout),
        )
        return queue


# _____________________ Resource Conector Builder ________________________

ConnectorType = TypeVar("ConnectorType", bound=ResourceConnector)


class ResourceConnectorBuilder(ABC, Generic[ConnectorType]):
    def __init__(
        self,
        context: "AppConstruct",
        connector: ConnectorType,
        lambda_: aws_lambda.Function,
    ) -> None:
        self.context = context
        self.connector = connector
        self.lambda_ = lambda_

    @abstractmethod
    def build(self):
        ...


class SqsConnectorBuilder(ResourceConnectorBuilder[SqsConnector]):
    def build(self):
        # TODO: validate resource type
        resource: aws_sqs.Queue = self.context.get_built_resource(
            self.connector.resource_name
        )
        if self.connector.permission in [SqsPermission.read, SqsPermission.full_access]:
            resource.grant_consume_messages(self.lambda_)
        if self.connector.permission in [
            SqsPermission.write,
            SqsPermission.full_access,
        ]:
            resource.grant_send_messages(self.lambda_)
        self.lambda_.add_environment(
            f"{self.connector.resource_name.upper()}_URL", resource.queue_url
        )
