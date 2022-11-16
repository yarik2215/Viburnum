s3_worker_template = """from viburnum.application import s3_handler, S3EventSequence


@s3_handler("{bucket_name}")
def {handler_name}(events: S3EventSequence):
    for e in events:
        print(e.object.key)
"""
