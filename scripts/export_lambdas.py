import boto3
import requests
import os
import json

EXPORT_FOLDER = os.getenv("EXPORT_FOLDER", "exports")
os.makedirs(f"{EXPORT_FOLDER}/lambdas", exist_ok=True)

lambda_client = boto3.client("lambda")
iam_client = boto3.client("iam")

# === Leer lista de Lambdas desde resources.json ===
with open("resources.json") as f:
    resources = json.load(f)

lambda_names = resources.get("lambdas", [])
results = []

for name in lambda_names:
    print(f"📦 Exportando Lambda: {name}")
    try:
        resp = lambda_client.get_function(FunctionName=name)

        # Descargar el código ZIP
        code_url = resp["Code"]["Location"]
        zip_path = f"{EXPORT_FOLDER}/lambdas/{name}.zip"
        r = requests.get(code_url)
        with open(zip_path, "wb") as f:
            f.write(r.content)

        # Obtener información del rol
        role_arn = resp["Configuration"]["Role"]
        role_name = role_arn.split("/")[-1]
        role_data = iam_client.get_role(RoleName=role_name)["Role"]

        # Políticas administradas adjuntas
        attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)["AttachedPolicies"]

        # Políticas inline
        inline_policy_names = iam_client.list_role_policies(RoleName=role_name)["PolicyNames"]
        inline_policies = {}
        for pol_name in inline_policy_names:
            pol_doc = iam_client.get_role_policy(RoleName=role_name, PolicyName=pol_name)["PolicyDocument"]
            inline_policies[pol_name] = pol_doc

        # Guardar configuración completa con políticas
        export_data = {
            "FunctionName": resp["Configuration"]["FunctionName"],
            "Configuration": resp["Configuration"],
            "Role": role_data,
            "AttachedPolicies": attached_policies,
            "InlinePolicies": inline_policies
        }

        config_path = f"{EXPORT_FOLDER}/lambdas/{name}.json"
        with open(config_path, "w") as f:
            json.dump(export_data, f, indent=2, default=str)  # convierte datetime a string

        results.append({"name": name, "status": "success"})
        print(f"✅ Lambda exportada con éxito: {name}")

    except Exception as e:
        print(f"❌ Error exportando {name}: {e}")
        results.append({"name": name, "status": "error", "error": str(e)})

# === Guardar log general ===
summary_path = f"{EXPORT_FOLDER}/lambdas/summary.json"
with open(summary_path, "w") as f:
    json.dump(results, f, indent=2, default=str)

print("🎉 Exportación completada con éxito.")
