import boto3
import json
import os
import zipfile
from botocore.exceptions import ClientError

DEST_PROFILE = "brp-dev"  # Perfil destino (ajusta si usas roles desde GitHub)
REGION = "us-east-1"
EXPORT_FOLDER = os.getenv("IMPORT_FOLDER", "exports/lambdas")

session = boto3.Session(profile_name=DEST_PROFILE, region_name=REGION)
lambda_client = session.client("lambda")
iam_client = session.client("iam")

# ID de la cuenta destino
sts_client = session.client("sts")
DEST_ACCOUNT_ID = sts_client.get_caller_identity()["Account"]

def ensure_role_exists(role_arn):
    """Valida si el rol existe, y si no, lo crea con el nuevo account ID"""
    role_name = role_arn.split("/")[-1]

    try:
        iam_client.get_role(RoleName=role_name)
        print(f"✅ Rol existente: {role_name}")
    except ClientError:
        print(f"⚙️  Creando rol: {role_name}")
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
        )

        # Agregar políticas básicas
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        )
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
        )
        print(f"✅ Rol creado: {role_name}")

    return f"arn:aws:iam::{DEST_ACCOUNT_ID}:role/{role_name}"

def import_lambda_from_json(json_path, zip_path):
    with open(json_path) as f:
        config = json.load(f)

    name = config["FunctionName"]
    role_arn = config["Role"]
    role_arn = ensure_role_exists(role_arn)

    try:
        with open(zip_path, "rb") as f:
            code_bytes = f.read()

        # Intentar actualizar si ya existe
        try:
            lambda_client.get_function(FunctionName=name)
            print(f"🔄 Actualizando Lambda existente: {name}")
            lambda_client.update_function_code(
                FunctionName=name,
                ZipFile=code_bytes
            )
            lambda_client.update_function_configuration(
                FunctionName=name,
                Role=role_arn,
                Handler=config["Handler"],
                Runtime=config["Runtime"],
                Timeout=config.get("Timeout", 3),
                MemorySize=config.get("MemorySize", 128),
                Environment=config.get("Environment", {})
            )
        except ClientError:
            print(f"🚀 Creando nueva Lambda: {name}")
            lambda_client.create_function(
                FunctionName=name,
                Runtime=config["Runtime"],
                Role=role_arn,
                Handler=config["Handler"],
                Code={"ZipFile": code_bytes},
                Description=config.get("Description", ""),
                Timeout=config.get("Timeout", 3),
                MemorySize=config.get("MemorySize", 128),
                Environment=config.get("Environment", {})
            )

        print(f"✅ Lambda importada: {name}")

    except Exception as e:
        print(f"❌ Error importando {name}: {e}")

# === MAIN ===
for file in os.listdir(EXPORT_FOLDER):
    if file.endswith(".json"):
        json_path = os.path.join(EXPORT_FOLDER, file)
        zip_path = json_path.replace(".json", ".zip")
        if os.path.exists(zip_path):
            import_lambda_from_json(json_path, zip_path)
