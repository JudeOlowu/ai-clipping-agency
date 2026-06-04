import os, requests
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv('RUNPOD_API_KEY')
ENDPOINT_ID = os.getenv('RUNPOD_ENDPOINT_ID')
url = 'https://api.runpod.io/graphql'
headers = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}

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
update_query = f"""
mutation {{
    saveEndpoint(
        input: {{
            id: "{ENDPOINT_ID}",
            name: "AI-Clipping-Agency-Endpoint",
            templateId: "{new_template_id}",
            gpuIds: "AMPERE_16,AMPERE_24,ADA_24",
            networkVolumeId: "",
            locations: "EU-RO-1,US-KS-1,US-KS-2",
            idleTimeout: 5,
            scalerType: "QUEUE_DELAY",
            scalerValue: 2,
            workersMin: 0,
            workersMax: 3
        }}
    ) {{
        id
        name
    }}
}}
"""
print("Updating endpoint to use new template...")
res2 = requests.post(url, json={'query': update_query}, headers=headers).json()
print('Update Endpoint Response:', res2)
