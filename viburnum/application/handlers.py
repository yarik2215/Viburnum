import enum
import json
from collections import UserList
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable, Optional

from viburnum.application.base import Handler, LambdaInput, LambdaOutput
from viburnum.application.types import HeadersType, JsonData, MultiQueryParamsType

# ___________________ API __________________________
# Lambda with Rest Api
# https://docs.aws.amazon.com/lambda/latest/dg/services-apigateway.html#apigateway-example-event


class Request(LambdaInput):
    def __init__(self, event: dict, context: dict) -> None:
        super().__init__(event, context)
        self._json = None

    @property
    def raw_headers(self) -> HeadersType:
        return self.event["headers"]

    @property
    def raw_query_params(self) -> MultiQueryParamsType:
        return self.event["multiValueQueryStringParameters"]

    @property
    def method(self) -> str:
        return self.event["httpMethod"]

    @property
    def path(self) -> str:
        return self.event["path"]

    @property
    def path_params(self) -> dict:
        return self.event["pathParameters"] or {}

    @property
    def body(self) -> Optional[str]:
        return self.event["body"]

    def json(self) -> JsonData:
        if not self.body:
            return None
        if not self._json:
            self._json = json.loads(self.body)
        return self._json


class Response(LambdaOutput):
    def __init__(
        self,
        status_code: int,
        body: dict,
        headers: dict = None,
    ) -> None:
        # TODO: add support for multivalue headers
        self.response_data = {
            "statusCode": status_code,
            "headers": headers or {},
            "isBase64Encoded": False,
            "body": json.dumps(body),
        }

    def as_response(self) -> dict:
        return self.response_data


class ApiHandler(Handler):
    event_class = Request

    def __init__(
        self,
        func: Callable,
        path: str,
        methods: Iterable[str],
    ) -> None:
        self.path: str = path
        self.methods: Iterable[str] = methods
        super().__init__(func)

    @staticmethod
    def _name_suffix() -> str:
        return "_api"


def route(path: str, methods: Iterable[str] = ("ANY",)):
    "Wrapper for creating :class:`ApiHandler` resource."

    def wraper(func):
        return ApiHandler(func, path, methods)

    return wraper


# ___________________ Job ______________________________
# Lambda with EventBridge
# https://docs.aws.amazon.com/lambda/latest/dg/services-cloudwatchevents.html


class JobEvent(LambdaInput):
    @property
    def detail(self) -> dict[str, Any]:
        return self.event["detail"]


class JobHandler(Handler):
    event_class = JobEvent

    def __init__(self, func: Callable, schedule: str) -> None:
        self.schedule = schedule
        super().__init__(func)

    @staticmethod
    def _name_suffix() -> str:
        return "_job"


def job(schedule: str):
    """
    Wrapper for creating :class:`JobHandler` resource.
    Schedule expression [docs](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html)
    """

    def wrapper(func):
        return JobHandler(func, schedule)

    return wrapper


# __________________ Sqs Worker ____________________________
# Lambda with SQS
# https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html


class QueueEvent:
    def __init__(self, event: dict) -> None:
        self.event = event
        self._body = None

    def delete(self):
        pass
        # TODO: delete event from queue

    @property
    def message_id(self) -> str:
        return self.event["messageId"]

    @property
    def body(self) -> JsonData:
        if self._body is None:
            try:
                self._body = json.loads(self.event["body"])
            except json.JSONDecodeError:
                self._body = self.event["body"]
        return self._body

    @property
    def attributes(self) -> dict[str, Any]:
        return self.event["attributes"]

    @property
    def message_attributes(self) -> dict[str, Any]:
        return self.event["messageAttributes"]


class SqsEventsSequence(LambdaInput, UserList[QueueEvent]):
    def __init__(self, event: dict, context: dict) -> None:
        super().__init__(event, context)
        self.data = [QueueEvent(e) for e in self.event["Records"]]


class SqsFailedEvents:
    # Returns from lambda failed events
    # https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html#services-sqs-batchfailurereporting

    def __init__(self, *failed_ids: tuple[str]) -> None:
        self.failed_event_ids: set[str] = set(failed_ids)

    def fail(self, *failed_ids: tuple[str]):
        self.failed_event_ids.update(failed_ids)

    def as_response(self) -> dict:
        return {
            "batchItemFailures": [
                {"itemIdentifier": id for id in self.failed_event_ids}
            ]
        }


class SqsHandler(Handler):
    event_class = SqsEventsSequence

    @staticmethod
    def _name_suffix() -> str:
        return "_worker"

    def __init__(self, func: Callable, queue_name: str) -> None:
        self.queue_name = queue_name
        super().__init__(func)


def sqs_handler(queue_name: str):
    """
    Wrapper for creating :class:`JobHandler` resource.
    """

    def wrapper(func):
        return SqsHandler(
            func,
            queue_name,
        )

    return wrapper


# _________________ S3 Worker ____________________________
# Lambda with S3 stream
# https://docs.aws.amazon.com/lambda/latest/dg/with-s3.html


class S3EventType(enum.Enum):
    """Notification event types.

    :link: https://docs.aws.amazon.com/AmazonS3/latest/userguide/notification-how-to-event-types-and-destinations.html#supported-notification-event-types
    """

    OBJECT_CREATED = "OBJECT_CREATED"
    OBJECT_CREATED_PUT = "OBJECT_CREATED_PUT"
    OBJECT_CREATED_POST = "OBJECT_CREATED_POST"
    OBJECT_CREATED_COPY = "OBJECT_CREATED_COPY"
    OBJECT_CREATED_COMPLETE_MULTIPART_UPLOAD = (
        "OBJECT_CREATED_COMPLETE_MULTIPART_UPLOAD"
    )
    OBJECT_REMOVED = "OBJECT_REMOVED"
    OBJECT_REMOVED_DELETE = "OBJECT_REMOVED_DELETE"
    OBJECT_REMOVED_DELETE_MARKER_CREATED = "OBJECT_REMOVED_DELETE_MARKER_CREATED"
    OBJECT_RESTORE_POST = "OBJECT_RESTORE_POST"
    OBJECT_RESTORE_COMPLETED = "OBJECT_RESTORE_COMPLETED"
    OBJECT_RESTORE_DELETE = "OBJECT_RESTORE_DELETE"
    REDUCED_REDUNDANCY_LOST_OBJECT = "REDUCED_REDUNDANCY_LOST_OBJECT"
    REPLICATION_OPERATION_FAILED_REPLICATION = (
        "REPLICATION_OPERATION_FAILED_REPLICATION"
    )
    REPLICATION_OPERATION_MISSED_THRESHOLD = "REPLICATION_OPERATION_MISSED_THRESHOLD"
    REPLICATION_OPERATION_REPLICATED_AFTER_THRESHOLD = (
        "REPLICATION_OPERATION_REPLICATED_AFTER_THRESHOLD"
    )
    REPLICATION_OPERATION_NOT_TRACKED = "REPLICATION_OPERATION_NOT_TRACKED"
    LIFECYCLE_EXPIRATION = "LIFECYCLE_EXPIRATION"
    LIFECYCLE_EXPIRATION_DELETE = "LIFECYCLE_EXPIRATION_DELETE"
    LIFECYCLE_EXPIRATION_DELETE_MARKER_CREATED = (
        "LIFECYCLE_EXPIRATION_DELETE_MARKER_CREATED"
    )
    LIFECYCLE_TRANSITION = "LIFECYCLE_TRANSITION"
    INTELLIGENT_TIERING = "INTELLIGENT_TIERING"
    OBJECT_TAGGING = "OBJECT_TAGGING"
    OBJECT_TAGGING_PUT = "OBJECT_TAGGING_PUT"
    OBJECT_TAGGING_DELETE = "OBJECT_TAGGING_DELETE"
    OBJECT_ACL_PUT = "OBJECT_ACL_PUT"


@dataclass
class S3Object:
    key: str
    size: int
    eTag: str
    sequencer: str


@dataclass
class S3Bucket:
    name: str
    arn: str


@dataclass
class S3Event:
    event_name: str
    event_time: datetime
    bucket: S3Bucket
    object: S3Object


class S3EventSequence(LambdaInput, UserList[S3Event]):
    def __init__(self, event: dict, context: dict) -> None:
        super().__init__(event, context)
        self.data = [self._get_s3_event(e) for e in event["Records"]]

    def _get_s3_event(self, raw_event: dict) -> S3Event:
        bucket = S3Bucket(
            name=raw_event["s3"]["bucket"]["name"], arn=raw_event["s3"]["bucket"]["arn"]
        )
        object_ = S3Object(**raw_event["s3"]["object"])
        return S3Event(
            event_name=raw_event.get("eventName"),
            event_time=datetime.strptime(
                raw_event.get("eventTime"), "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            bucket=bucket,
            object=object_,
        )


class S3Handler(Handler):
    event_class = SqsEventsSequence

    def __init__(
        self, func: Callable, bucket_name: str, events: list[S3EventType]
    ) -> None:
        super().__init__(func)
        self.bucket_name = bucket_name
        self.events = events


def s3_handler(
    bucket_name: str, events: Iterable[S3EventType] = (S3EventType.OBJECT_CREATED,)
):
    """
    Wrapper for creating :class:`JobHandler` resource.
    """

    def wrapper(func):
        return S3Handler(
            func,
            bucket_name,
            events,
        )

    return wrapper
