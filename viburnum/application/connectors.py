import enum
import os

import boto3

from .base import Handler, ResourceConnector

# ______________________ SQS _______________________________


class SqsPermission(enum.Enum):
    read = 1
    write = 2
    full_access = 3


class SqsConnector(ResourceConnector):
    def __init__(
        self, handler: Handler, resource_name: str, permission: SqsPermission
    ) -> None:
        super().__init__(handler, resource_name)
        self.permission = permission

    def get_resource_client(self):
        if not self._client:
            queue_url = os.environ[f"{self.resource_name.upper()}_URL"]
            sqs = boto3.resource("sqs")
            self._client = sqs.Queue(queue_url)
        return self._client


def sqs(
    queue_name: str,
    permission: SqsPermission = SqsPermission.read,
    # *,
    # attr_name: str = None,
):
    "Add queue `Sqs` resource for :class:`Handler`"

    def wraper(handler: Handler):
        # FIXME: rework how we pass resources into handler
        # handler.extra_kwargs[attr_name or queue_name] = get_queue(queue_name)
        SqsConnector(handler, queue_name, permission)
        return handler

    return wraper
