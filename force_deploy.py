import os, requests
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv('RUNPOD_API_KEY')
ENDPOINT_ID = os.getenv('RUNPOD_ENDPOINT_ID')
url = 'https://api.runpod.io/graphql'
headers = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')

import time
import subprocess

# Fetch the latest commit SHA from the local git repo
latest_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip().decode('utf-8')
image_name_with_tag = f"ghcr.io/judeolowu/ai-clipping-agency:{latest_sha}"
print(f"Deploying image: {image_name_with_tag}")

template_name = f"AI-Clipping-Worker-V{int(time.time())}"
# 1. Create a new Template to force a new release and inject the AI key
template_query = f"""
mutation {{
    saveTemplate(
        input: {{
            name: "{template_name}",
            imageName: "{image_name_with_tag}",
            containerRegistryAuthId: "cmpxxd7du00251w4gumhmxo69",
            dockerArgs: "",
            containerDiskInGb: 20,
            volumeInGb: 0,
            isServerless: true,
            env: [
                {{key: "CACHE_BUST", value: "4"}},
                {{key: "OPENROUTER_API_KEY", value: "{OPENROUTER_API_KEY}"}}
            ]
        }}
    ) {{
        id
        name
    }}
}}
"""
print("Creating new template...")
res = requests.post(url, json={'query': template_query}, headers=headers).json()
print('Create Template Response:', res)

new_template_id = res['data']['saveTemplate']['id']

# 2. Update Endpoint to use new Template
print(f"Updating endpoint {ENDPOINT_ID} to use new template {new_template_id}...")
import runpod
runpod.api_key = API_KEY
runpod.update_endpoint_template(ENDPOINT_ID, new_template_id)
print("Endpoint template successfully updated via Python SDK!")

