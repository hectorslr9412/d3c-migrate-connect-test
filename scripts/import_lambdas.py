import boto3
import json
import os
import time
from botocore.exceptions import ClientError

# === CONFIG ===
IMPORT_FOLDER = os.getenv("IMPORT_FOLDER", "exports/tmp/lambdas")
REGION = os.getenv("AWS_REGION", "us-east-1")

lambda_client = boto3.client("lambda", region_name=REGION)
iam_client = boto3.client("iam", region_name=REGION)
sts_client = boto3.client("sts", region_name=REGION)

ACCOUNT_ID = sts_client.get_caller_identity()["Account"]

# === FUNCIONES ===
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

def ensure_role(role_data, attached_policies, inline_policies):
    """Create or ensure IAM role exists with policies"""
    role_name = role_data["RoleName"]
    try:
        iam_client.get_role(RoleName=role_name)
        print(f"✅ Role '{role_name}' ya existe.")
    except ClientError:
        print(f"⚙️ Creando role '{role_name}'...")
        iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(role_data["AssumeRolePolicyDocument"]),
            Description=role_data.get("Description", "Imported from export"),
        )
        time.sleep(3)

    # Adjuntar managed policies
    for p in attached_policies:
        arn = p["PolicyArn"]
        # Reemplazar account ID si no es policy de AWS
        if ":aws:" not in arn:
            arn = arn.replace(role_data["Arn"].split(":")[4], ACCOUNT_ID)
        try:
            iam_client.attach_role_policy(RoleName=role_name, PolicyArn=arn)
        except ClientError:
            pass

    # Inline policies
    for pol_name, pol_doc in inline_policies.items():
        try:
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=pol_name,
                PolicyDocument=json.dumps(pol_doc)
            )
        except ClientError:
            pass

    return f"arn:aws:iam::{ACCOUNT_ID}:role/{role_name}"

# === LOOP PRINCIPAL DE IMPORTACIÓN ===
files = [f for f in os.listdir(IMPORT_FOLDER) if f.endswith(".json") and f != "summary.json"]

for f_name in files:
    print(f"\n📂 Procesando archivo: {f_name}")
    path = os.path.join(IMPORT_FOLDER, f_name)
    with open(path) as f:
        data = json.load(f)

    name = data["FunctionName"]
    config = data["Configuration"]
    role = data["Role"]
    attached_policies = data.get("AttachedPolicies", [])
    inline_policies = data.get("InlinePolicies", {})

    print(f"\n=== Importando Lambda: {name} ===")

    # Asegurar que el rol exista
    dest_role_arn = ensure_role(role, attached_policies, inline_policies)

    # Verificar ZIP
    zip_file = os.path.join(IMPORT_FOLDER, f"{name}.zip")
    if not os.path.exists(zip_file):
        print(f"❌ No se encontró el archivo ZIP para {name}, se omite.")
        continue

    with open(zip_file, "rb") as z:
        code_bytes = z.read()

    # Verificar si la Lambda existe
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
            Role=dest_role_arn,
            Handler=config["Handler"],
            Code={"ZipFile": code_bytes},
            Description=config.get("Description", ""),
            Timeout=config.get("Timeout", 3),
            MemorySize=config.get("MemorySize", 128),
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
            Role=dest_role_arn,
            Handler=config["Handler"],
            Description=config.get("Description", ""),
            Timeout=config.get("Timeout", 3),
            MemorySize=config.get("MemorySize", 128),
            Environment=config.get("Environment", {}),
            Layers=config.get("Layers", []),
            Runtime=config["Runtime"],
        )
        wait_for_lambda(name)

    print(f"✅ Lambda {name} importada correctamente.")

print("\n🎉 Importación completada con éxito.")
