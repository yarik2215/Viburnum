sqs_worker_template = """from viburnum.application import sqs_handler, SqsEventsSequence


@sqs_handler("{sqs_name}")
def {handler_name}(events: SqsEventsSequence):
    for e in events:
        print(e.message_id)
        print(e.body)
"""
