import os
import time
import json
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('RUNPOD_API_KEY')
ENDPOINT_ID = os.getenv('RUNPOD_ENDPOINT_ID')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
MEMORY_FILE = 'agent_memory.json'

HEADERS = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    return {'errors': []}

def save_memory(memory):
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=4)

def check_runpod_health():
    url = f'https://api.runpod.ai/v2/{ENDPOINT_ID}/health'
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        return res.json()
    except Exception as e:
        return {'error': str(e)}

def analyze_error_with_llama(error_data, memory):
    prompt = f'''You are an expert DevOps AI managing a RunPod deployment.
Error: {json.dumps(error_data)}
Memory: {json.dumps(memory['errors'])}
If known, return exact fix. If new, diagnose and provide 1-sentence fix.'''
    
    try:
        import openai
        client = openai.OpenAI(base_url='https://openrouter.ai/api/v1', api_key=OPENROUTER_API_KEY)
        response = client.chat.completions.create(
            model='meta-llama/llama-3.3-70b-instruct',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f'Failed to reach OpenRouter: {e}'

def main():
    print('Starting Evolving Cloud Monitor Agent...')
    while True:
        health = check_runpod_health()
        workers = health.get('workers', {}).get('running', 0)
        
        print(f'[Health Check] Running Workers: {workers}')
        
        if 'error' in health or workers == 0:
            print('!!! CLOUD ANOMALY DETECTED !!!')
            memory = load_memory()
            diagnosis = analyze_error_with_llama(health, memory)
            print(f'--> AI DIAGNOSIS: {diagnosis}')
            
            memory['errors'].append({'time': time.time(), 'error': str(health), 'fix': diagnosis})
            save_memory(memory)
            time.sleep(60)
        else:
            time.sleep(30)

if __name__ == '__main__':
    main()
