#!/usr/bin/env python3
import boto3
import requests
import json
import os
from datetime import datetime

# ===== VARIABLES DEL WORKFLOW =====
ENVIRONMENT = os.getenv("ENVIRONMENT")
CONNECT_INSTANCE_ID = os.getenv("CONNECT_INSTANCE_ID")

if not ENVIRONMENT or not CONNECT_INSTANCE_ID:
    print("Faltan variables de entorno")
    exit(1)

# ===== CARPETA: prod-2025-04-05 =====
timestamp = datetime.now().strftime("%Y-%m-%d")
export_folder = f"exports/{ENVIRONMENT}-{timestamp}"
lambdas_folder = f"{export_folder}/lambdas"
flows_folder = f"{export_folder}/Flows"

os.makedirs(lambdas_folder, exist_ok=True)
os.makedirs(flows_folder, exist_ok=True)

# ===== CLIENTES (autenticado por assumeRole) =====
session = boto3.Session()  # Credenciales de OIDC
lambda_client = session.client("lambda")
connect_client = session.client("connect")

# ===== EXPORTAR LAMBDAS =====
with open("lambdas.txt") as f:
    lambda_names = [line.strip() for line in f if line.strip()]

for name in lambda_names:
    try:
        resp = lambda_client.get_function(FunctionName=name)
        code_url = resp["Code"]["Location"]
        zip_path = f"{lambdas_folder}/{name}.zip"
        r = requests.get(code_url)
        with open(zip_path, "wb") as f:
            f.write(r.content)
        print(f"Lambda: {name}")
    except Exception as e:
        print(f"ERROR Lambda {name}: {e}")

# ===== config.json =====
with open(f"{export_folder}/config.json", "w") as f:
    json.dump({
        "source_environment": ENVIRONMENT,
        "export_date": timestamp,
        "connectInstanceId": CONNECT_INSTANCE_ID,
        "lambdas": lambda_names
    }, f, indent=2)

print(f"\nExportado: {export_folder}")