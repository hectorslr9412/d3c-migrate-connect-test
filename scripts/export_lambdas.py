import boto3
import requests
import os
import json

# === Create export folder structure ===
EXPORT_FOLDER = os.getenv("EXPORT_FOLDER", "exports")
os.makedirs(f"{EXPORT_FOLDER}/lambdas", exist_ok=True)

lambda_client = boto3.client("lambda")
iam_client = boto3.client("iam")

# === Read Lambda list from resources.json ===
with open("resources.json") as f:
    resources = json.load(f)

lambda_names = resources.get("lambdas", [])
results = []

for name in lambda_names:
    print(f"📦 Exporting Lambda: {name}")
    try:
        resp = lambda_client.get_function(FunctionName=name)

        # === Download Lambda ZIP code ===
        code_url = resp["Code"]["Location"]
        zip_path = f"{EXPORT_FOLDER}/lambdas/{name}.zip"
        r = requests.get(code_url)
        with open(zip_path, "wb") as f:
            f.write(r.content)

        # === Get IAM role information ===
        role_arn = resp["Configuration"]["Role"]
        role_name = role_arn.split("/")[-1]
        role_data = iam_client.get_role(RoleName=role_name)["Role"]

        # === Get attached managed policies ===
        attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)["AttachedPolicies"]

        # === Get inline policies ===
        inline_policy_names = iam_client.list_role_policies(RoleName=role_name)["PolicyNames"]
        inline_policies = {}
        for pol_name in inline_policy_names:
            pol_doc = iam_client.get_role_policy(RoleName=role_name, PolicyName=pol_name)["PolicyDocument"]
            inline_policies[pol_name] = pol_doc

        # === Save complete configuration including policies ===
        export_data = {
            "FunctionName": resp["Configuration"]["FunctionName"],
            "Configuration": resp["Configuration"],
            "Role": role_data,
            "AttachedPolicies": attached_policies,
            "InlinePolicies": inline_policies
        }

        config_path = f"{EXPORT_FOLDER}/lambdas/{name}.json"
        with open(config_path, "w") as f:
            json.dump(export_data, f, indent=2, default=str)  # converts datetime to string

        results.append({"name": name, "status": "success"})
        print(f"✅ Lambda successfully exported: {name}")

    except Exception as e:
        print(f"❌ Error exporting {name}: {e}")
        results.append({"name": name, "status": "error", "error": str(e)})

# === Save general summary log ===
summary_path = f"{EXPORT_FOLDER}/lambdas/summary.json"
with open(summary_path, "w") as f:
    json.dump(results, f, indent=2, default=str)

print("🎉 Export completed successfully.")
