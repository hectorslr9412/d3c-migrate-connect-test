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

# === FUNCTIONS ===
def wait_for_lambda(function_name, timeout=60):
    """Wait until the Lambda function is ready for updates"""
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
    """Create or ensure that the IAM role exists with its policies updated"""
    role_name = role_data["RoleName"]

    try:
        iam_client.get_role(RoleName=role_name)
        print(f"✅ Role '{role_name}' already exists.")
    except ClientError:
        print(f"⚙️ Creating role '{role_name}'...")
        iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(role_data["AssumeRolePolicyDocument"]),
            Description=role_data.get("Description", "Imported from export"),
        )
        time.sleep(30)

    # === Attach Managed Policies ===
    for p in attached_policies:
        policy_name = p["PolicyName"]
        policy_arn = p["PolicyArn"]

        # If the policy is not global (aws), replace the source account ID with the destination account ID
        if ":aws:" not in policy_arn:
            src_account = role_data["Arn"].split(":")[4]
            policy_arn = policy_arn.replace(src_account, ACCOUNT_ID)

        try:
            # Check if the policy exists before attaching it
            iam_client.get_policy(PolicyArn=policy_arn)
            iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            print(f"✅ Policy '{policy_name}' attached to role '{role_name}'.")
        except ClientError as e:
            print(f"⚠️ Policy '{policy_name}' not found. Using AWSLambdaBasicExecutionRole instead.")
            try:
                iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                )
            except ClientError as e2:
                print(f"❌ Failed to attach default policy: {e2}")

    # === Inline Policies ===
    for pol_name, pol_doc in inline_policies.items():
        pol_doc_str = json.dumps(pol_doc)
        src_account = role_data["Arn"].split(":")[4]

        # Replace any ARN with the destination account ID
        pol_doc_str = pol_doc_str.replace(src_account, ACCOUNT_ID)

        try:
            iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=pol_name,
                PolicyDocument=pol_doc_str
            )
            print(f"✅ Inline policy '{pol_name}' updated in '{role_name}'.")
        except ClientError as e:
            print(f"❌ Error applying inline policy '{pol_name}': {e}")

    return f"arn:aws:iam::{ACCOUNT_ID}:role/{role_name}"


# === MAIN IMPORT LOOP ===
files = [f for f in os.listdir(IMPORT_FOLDER) if f.endswith(".json") and f != "summary.json"]

for f_name in files:
    print(f"\n📂 Processing file: {f_name}")
    path = os.path.join(IMPORT_FOLDER, f_name)
    with open(path) as f:
        data = json.load(f)

    name = data["FunctionName"]
    config = data["Configuration"]
    role = data["Role"]
    attached_policies = data.get("AttachedPolicies", [])
    inline_policies = data.get("InlinePolicies", {})

    print(f"\n=== Importing Lambda: {name} ===")

    # Ensure the IAM role exists
    dest_role_arn = ensure_role(role, attached_policies, inline_policies)

    # Check ZIP file
    zip_file = os.path.join(IMPORT_FOLDER, f"{name}.zip")
    if not os.path.exists(zip_file):
        print(f"❌ ZIP file not found for {name}, skipping.")
        continue

    with open(zip_file, "rb") as z:
        code_bytes = z.read()

    # Check if the Lambda already exists
    exists = True
    try:
        lambda_client.get_function(FunctionName=name)
    except lambda_client.exceptions.ResourceNotFoundException:
        exists = False

    if not exists:
        print(f"🚀 Creating Lambda {name}...")
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
        print(f"🔁 Updating Lambda {name}...")
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

    print(f"✅ Lambda {name} successfully imported.")

print("\n🎉 Import completed successfully.")
