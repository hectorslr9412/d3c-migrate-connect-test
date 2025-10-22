#!/usr/bin/env python3
import boto3
import zipfile
import os

RELEASE_FOLDER = os.getenv("RELEASE_FOLDER")
ENV = os.getenv("ENVIRONMENT")

if not RELEASE_FOLDER:
    print("ERROR: RELEASE_FOLDER no definido")
    exit(1)

lambda_client = boto3.client("lambda")

for zip_file in os.listdir(f"{RELEASE_FOLDER}/lambdas"):
    name = zip_file.replace(".zip", "")
    zip_path = f"{RELEASE_FOLDER}/lambdas/{zip_file}"
    
    try:
        with open(zip_path, "rb") as f:
            code = f.read()
        
        try:
            lambda_client.create_function(
                FunctionName=name,
                Runtime="python3.11",
                Role=f"arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:role/LambdaRole",
                Handler="lambda_function.lambda_handler",
                Code={"ZipFile": code},
                Timeout=30,
                MemorySize=256
            )
            print(f"Creada: {name}")
        except lambda_client.exceptions.ResourceConflictException:
            lambda_client.update_function_code(
                FunctionName=name,
                ZipFile=code
            )
            print(f"Actualizada: {name}")
    except Exception as e:
        print(f"ERROR {name}: {e}")