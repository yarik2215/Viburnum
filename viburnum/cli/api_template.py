api_template = """from viburnum.application import route, Request, Response


@route("{path}", methods={methods})
def {handler_name}(request: Request) -> Response:
    return Response(200, {{}})

"""
