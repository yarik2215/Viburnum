job_template = """from viburnum.application import JobEvent, job


@job("{schedule}")
def {handler_name}(event: JobEvent):
    print("Hello world")
"""
