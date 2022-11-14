# Viburnum

**Viburum** - it's a small framework built on top of AWS CDK to simplify development and deploying AWS Serverless web applications.

## Installing

Package consist of two pats `primitives` that help to describe your handlers and resources and `deployer` that will convert primitives into CloudFormation using CDK.

### Installing only primitives

```bash
pip install viburnum
```

### Installing with deployer

```bash
pip install "viburnum[deployer]"
```

Lambda function will require only primitives to work correctly. That's why it's recommended to add `viburnum` into `requirements.txt` and `viburnum[deployer]` into `requirements-dev.txt`

## Project structure

Each Lambda function handler is represented as folder with `handler.py` inside and other files if required.

**Example** `handler.py`:

```python
from viburnum.application import Request, Response, route

@route("/tests/{id}", methods=["GET"])
def get_test(request: Request, test_queue):
    print(f"Get test: {request.path_params.get('id')}")
    return Response(200, {})
```

In the root folder you need to have `app.py` file with `Application`, this file used by deployer and CDK to determine all related resources.

**Example** `app.py`

```python
import aws_cdk as cdk
from viburnum.deployer.builders import AppConstruct
from viburnum.application import Application, Sqs

from functions.api.get_test.handler import get_test

app = Application("TestApp")
# Handlers
app.add_handler(get_test)

context = cdk.App()
AppConstruct(context, app)
context.synth()
```

All logic that shared across all lambdas, must be placed inside `shared` folder, and it will plugged into Lambda as a Layer.

### Recommended structure

```project
├── functions
│   ├── __init__.py
│   ├── api
│   │   ├── __init__.py
│   │   ├── some_api
│   │   │    ├── __init__.py
│   │   │    ├── handler.py
│   │   │    └── ...
│   │   │
│   │   └── ...
│   │   
│   ├── jobs
│   │   ├── __init__.py
│   │   ├── some_job
│   │   │    ├── __init__.py
│   │   │    ├── handler.py
│   │   │    └── ...
│   │   │
│   │   └── ...
│   │   
│   └── workers
│       ├── __init__.py
│       ├── some_job
│       │    ├── __init__.py
│       │    ├── handler.py
│       │    └── ...
│       │
│       └── ...
│      
├── shared
│   ├── __init__.py
│   └── ...
│
├── app.py
├── requirements-dev.txt
└── requirements.txt
```
