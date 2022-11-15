import enum
from pathlib import Path

import typer

from viburnum import __version__

from .api_template import api_template
from .app_template import app_template
from .job_template import job_template
from .sqs_worker_template import sqs_worker_template


def _create_moudle(path: Path):
    if not path.exists():
        path.mkdir(0o777, True, False)
    init_file = path.joinpath("__init__.py")
    if not init_file.exists():
        init_file.touch(777, True)


class ProjectInitializer:
    def __init__(self, without_shared: bool = False) -> None:
        typer.confirm("It will overwrite app.py file, continue?", abort=True)
        self.app_name = self._get_app_name()
        typer.secho("Initializing project...", fg=typer.colors.BRIGHT_CYAN)
        self._create_requirements()
        self._update_app()
        if not without_shared:
            self._create_shared_folder()
        typer.secho("Done!", fg=typer.colors.BRIGHT_CYAN)

    def _create_requirements(self) -> None:
        with open("requirements.txt", "w", encoding="utf-8") as f:
            f.write(f"viburnum>={__version__}")

    def _get_app_name(self) -> str:
        return typer.prompt("Stack name", type=str)

    def _update_app(self):
        with open(Path("./app.py"), "w", encoding="utf-8") as f:
            f.write(app_template.format(app_name=self.app_name))

    def _create_shared_folder(self):
        path = Path("./shared")
        _create_moudle(path)


app = typer.Typer(name="viburnum-cli")


@app.command(help="Initialize project")
def init(without_shared: bool = typer.Option(False, help="Don't create shared folder")):
    ProjectInitializer(without_shared)


class HandlerCreator:
    handler_type: str = "other"
    handler_file_template: str = "dummy"

    def __init__(self) -> None:
        self._read_params()
        self._create_handler_folder()
        self._create_handler_file()
        self._add_handler_into_app()

    def _read_params(self):
        # TODO: add regex validation
        self.handler_name = (
            typer.prompt("Function name", type=str)
            .strip()
            .replace(" ", "_")
            .replace("-", "_")
        )
        self.handler_path = Path(f"./functions/{self.handler_type}/{self.handler_name}")

    def _create_handler_folder(self):
        _create_moudle(self.handler_path.parent.parent)
        _create_moudle(self.handler_path.parent)
        _create_moudle(self.handler_path)

    def _get_params(self) -> dict:
        """Overload this methods in child classes"""
        return {"handler_name": self.handler_name}

    def _create_handler_file(self):
        with open(self.handler_path.joinpath("handler.py"), "x", encoding="utf-8") as f:
            f.write(self.handler_file_template.format(**self._get_params()))

    def _add_handler_into_app(self):
        file_data = ""
        with open(Path("./app.py"), "r", encoding="utf-8") as f:
            file_data = f.read()
        with open(Path("./app.py"), "w", encoding="utf-8") as f:
            import_path = f"{self.handler_path.as_posix().replace('/', '.')}.handler"
            f.write(
                file_data.replace(
                    "# [Handlers]",
                    f"# [Handlers]\napp.add_handler({self.handler_name})",
                ).replace(
                    "# [Imports]",
                    f"# [Imports]\nfrom {import_path} import {self.handler_name}",
                )
            )


create_handler_app = typer.Typer()


ALLOWED_METHODS = ["ANY", "GET", "POST", "PUT", "PATCH", "DELETE"]


class HttpMethods(str, enum.Enum):
    ANY = "ANY"
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


def _validate_methods(value: str):
    methods = value.upper().strip().split()
    if isinstance(methods, str):
        return [HttpMethods(methods).value]
    return [HttpMethods(m).value for m in methods if m]


class ApiHandlerCreator(HandlerCreator):
    handler_type: str = "api"
    handler_file_template: str = api_template

    def __init__(self) -> None:
        super().__init__()
        typer.secho(
            f"Created api handler '{self.handler_name}'\nRoute: {self.methods} {self.path}",
            fg=typer.colors.BRIGHT_GREEN,
        )

    def _read_params(self):
        super()._read_params()
        self.methods = self._get_methods()
        self.path: str = typer.prompt("Path").strip().replace(" ", "-")
        if not self.path.startswith("/"):
            self.path = f"/{self.path}"

    def _get_methods(self) -> list[str]:
        while True:
            try:
                methods: list[str] = typer.prompt(
                    "Methods",
                    default="ANY",
                    type=HttpMethods,
                    value_proc=_validate_methods,
                    show_choices=True,
                )
                return methods
            except ValueError as e:
                typer.secho(f"Wrong value {e.args[0]}", fg=typer.colors.RED)

    def _get_params(self) -> dict:
        params = super()._get_params()
        params.update({"methods": self.methods, "path": self.path})
        return params


class JobHandlerCreator(HandlerCreator):
    handler_type: str = "jobs"
    handler_file_template: str = job_template

    def __init__(self) -> None:
        super().__init__()
        typer.secho(
            f"Created job handler '{self.handler_name}'", fg=typer.colors.BRIGHT_GREEN
        )

    def _read_params(self):
        super()._read_params()
        self.schedule = typer.prompt("Schedule expression", type=str)

    def _get_params(self) -> dict:
        params = super()._get_params()
        params.update({"schedule": self.schedule})
        return params


class SqsWorkerHandlerCreator(HandlerCreator):
    handler_type: str = "workers"
    handler_file_template: str = sqs_worker_template

    def __init__(self) -> None:
        super().__init__()
        typer.secho(
            f"Created job handler '{self.handler_name}'", fg=typer.colors.BRIGHT_GREEN
        )

    def _read_params(self):
        super()._read_params()
        self.sqs_name = typer.prompt("Sqs name", type=str)

    def _get_params(self) -> dict:
        params = super()._get_params()
        params.update({"sqs_name": self.sqs_name})
        return params


@create_handler_app.command()
def api():
    ApiHandlerCreator()


@create_handler_app.command()
def job():
    JobHandlerCreator()


@create_handler_app.command()
def worker():
    SqsWorkerHandlerCreator()


app.add_typer(create_handler_app, name="add")


if __name__ == "__main__":
    app()
