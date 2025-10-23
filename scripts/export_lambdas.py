import boto3
import requests
import os
import json

EXPORT_FOLDER = os.getenv("EXPORT_FOLDER", "exports")
os.makedirs(f"{EXPORT_FOLDER}/lambdas", exist_ok=True)

lambda_client = boto3.client("lambda")

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

        # Guardar configuración limpia
        config_path = f"{EXPORT_FOLDER}/lambdas/{name}.json"
        with open(config_path, "w") as f:
            json.dump(resp["Configuration"], f, indent=2, default=str)  # 👈 convierte datetime a string

        results.append({"name": name, "status": "success"})
        print(f"✅ Lambda exportada: {name}")

    except Exception as e:
        print(f"❌ Error exportando {name}: {e}")
        results.append({"name": name, "status": "error", "error": str(e)})

# === Guardar log general ===
summary_path = f"{EXPORT_FOLDER}/lambdas/summary.json"
with open(summary_path, "w") as f:
    json.dump(results, f, indent=2, default=str)

print("🎉 Exportación completada con éxito.")
