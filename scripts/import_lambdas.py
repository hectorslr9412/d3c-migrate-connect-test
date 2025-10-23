import boto3
import json
import os
import time
from botocore.exceptions import ClientError

IMPORT_FOLDER = os.getenv("IMPORT_FOLDER", "exports/tmp/lambdas")
REGION = os.getenv("AWS_REGION", "us-east-1")

lambda_client = boto3.client("lambda", region_name=REGION)
iam_client = boto3.client("iam", region_name=REGION)
sts_client = boto3.client("sts", region_name=REGION)

ACCOUNT_ID = sts_client.get_caller_identity()["Account"]


def wait_for_lambda(function_name, timeout=60):
    """Wait until Lambda is ready for updates"""
    start = time.time()
    while True:
        try:
            state = lambda_client.get_function_configuration(FunctionName=function_name)
            status = state.get("LastUpdateStatus", "Successful")
            if status == "InProgress":
                time.sleep(2)
            elif status == "Failed":
                raise Exception(f"Lambda update failed: {state.get('LastUpdateStatusReason')}")
            else:
                break
        except ClientError:
            if time.time() - start > timeout:
                raise TimeoutError(f"Timeout waiting for Lambda {function_name}")
            time.sleep(2)


# === MAIN IMPORT LOOP ===
files = [f for f in os.listdir(IMPORT_FOLDER) if f.endswith(".json") and f != "summary.json"]

for f_name in files:
    print(f"📄 Procesando {f_name}...")
    path = f"{IMPORT_FOLDER}/{f_name}"
    with open(path) as f:
        data = json.load(f)

    # Extraer nombre y configuración
    name = data["FunctionName"]
    config = data

    # Validar ZIP
    zip_file = f"{IMPORT_FOLDER}/{name}.zip"
    if not os.path.exists(zip_file):
        print(f"❌ No se encontró el archivo ZIP para {name}, se omite.")
        continue

    with open(zip_file, "rb") as z:
        code_bytes = z.read()

    # Verificar si existe la Lambda
    exists = True
    try:
        lambda_client.get_function(FunctionName=name)
    except lambda_client.exceptions.ResourceNotFoundException:
        exists = False

    if not exists:
        print(f"🚀 Creando Lambda {name}...")
        lambda_client.create_function(
            FunctionName=name,
            Runtime=config["Runtime"],
            Role=config["Role"],  # Usa el mismo ARN del export
            Handler=config["Handler"],
            Code={"ZipFile": code_bytes},
            Description=config.get("Description", ""),
            Timeout=config["Timeout"],
            MemorySize=config["MemorySize"],
            Publish=True,
            Environment=config.get("Environment", {}),
            Layers=config.get("Layers", []),
            PackageType=config.get("PackageType", "Zip"),
            Architectures=config.get("Architectures", ["x86_64"]),
        )
    else:
        print(f"🔁 Actualizando Lambda {name}...")
        wait_for_lambda(name)
        lambda_client.update_function_code(FunctionName=name, ZipFile=code_bytes, Publish=True)
        wait_for_lambda(name)
        lambda_client.update_function_configuration(
            FunctionName=name,
            Role=config["Role"],
            Handler=config["Handler"],
            Description=config.get("Description", ""),
            Timeout=config["Timeout"],
            MemorySize=config["MemorySize"],
            Environment=config.get("Environment", {}),
            Layers=config.get("Layers", []),
            Runtime=config["Runtime"],
        )
        wait_for_lambda(name)

    print(f"✅ Lambda {name} importada correctamente.")

print("\n🎉 Importación completada con éxito.")
