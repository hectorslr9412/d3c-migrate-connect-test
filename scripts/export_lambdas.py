import boto3
import requests
import os
import json

EXPORT_FOLDER = os.getenv("EXPORT_FOLDER", "exports/tmp")
os.makedirs(f"{EXPORT_FOLDER}/lambdas", exist_ok=True)

with open("resources.json") as f:
    resources = json.load(f)

lambda_client = boto3.client("lambda")
iam_client = boto3.client("iam")

exported = []

for name in resources.get("lambdas", []):
    print(f"📦 Exportando Lambda: {name}")
    try:
        # Obtener configuración completa
        response = lambda_client.get_function(FunctionName=name)
        config = response["Configuration"]
        code_url = response["Code"]["Location"]

        # Guardar código
        zip_path = f"{EXPORT_FOLDER}/lambdas/{name}.zip"
        r = requests.get(code_url)
        with open(zip_path, "wb") as f:
            f.write(r.content)

        # Obtener rol y políticas
        role_arn = config["Role"]
        role_name = role_arn.split("/")[-1]
        role = iam_client.get_role(RoleName=role_name)["Role"]
        attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)["AttachedPolicies"]
        inline_policies = iam_client.list_role_policies(RoleName=role_name)["PolicyNames"]

        lambda_data = {
            "name": name,
            "config": config,
            "role": role,
            "attached_policies": attached_policies,
            "inline_policies": inline_policies
        }

        # Guardar JSON de configuración
        with open(f"{EXPORT_FOLDER}/lambdas/{name}.json", "w") as f:
            json.dump(lambda_data, f, indent=2)

        exported.append(name)
        print(f"✅ Lambda exportada: {name}")

    except Exception as e:
        print(f"❌ Error exportando {name}: {e}")

# Registrar lista de lambdas exportadas
with open(f"{EXPORT_FOLDER}/lambdas/exported_lambdas.json", "w") as f:
    json.dump(exported, f, indent=2)

print("\n🎉 Exportación completada con éxito.")
