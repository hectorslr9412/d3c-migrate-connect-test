#!/usr/bin/env python3
import boto3
import requests
import json
import os

EXPORT_FOLDER = os.getenv("EXPORT_FOLDER")
with open("resources.json") as f:
    resources = json.load(f)

lambda_client = boto3.client("lambda")

for name in resources.get("lambdas", []):
    print(name)
    try:
        resp = lambda_client.get_function(FunctionName=name)
        code_url = resp["Code"]["Location"]
        zip_path = f"{EXPORT_FOLDER}/lambdas/{name}.zip"
        r = requests.get(code_url)
        with open(zip_path, "wb") as f:
            f.write(r.content)
        print(f"Lambda: {name}")
    except Exception as e:
        print(f"ERROR Lambda {name}: {e}")