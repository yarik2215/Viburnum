from .base import Resource


class Sqs(Resource):
    def __init__(self, name: str, visibility_timeout: int = 360) -> None:
        super().__init__(name)
        self.visibility_timeout = visibility_timeout


class S3(Resource):
    pass
