import boto3
import json
import os

def get_lambda_info(function_name):
    client = boto3.client('lambda')
    
    try:
        response = client.get_function(FunctionName=function_name)
        function_info = response['Configuration']
        
        info = {
            "FunctionName": function_info['FunctionName'],
            "FunctionArn": function_info['FunctionArn'],
            "Runtime": function_info['Runtime'],
            "Handler": function_info['Handler'],
            "Role": function_info['Role'],
            "CodeSize": function_info['CodeSize'],
            "LastModified": function_info['LastModified'],
            "Timeout": function_info['Timeout'],
            "MemorySize": function_info['MemorySize'],
            "Description": function_info.get('Description', ''),
            "Environment": function_info.get('Environment', {}).get('Variables', {}),
            "Layers": [layer['Arn'] for layer in function_info.get('Layers', [])]
        }
        
        return info
    except client.exceptions.ResourceNotFoundException:
        print(f"Error: La función '{function_name}' no existe.")
        return None
    except Exception as e:
        print(f"Error inesperado: {e}")
        return None

if __name__ == "__main__":
    # Cambia este nombre o pásalo como argumento
    LAMBDA_NAME = os.getenv("LAMBDA_NAME", "mi-lambda-dev")  # por defecto
    
    info = get_lambda_info(LAMBDA_NAME)
    if info:
        print(json.dumps(info, indent=2, default=str))