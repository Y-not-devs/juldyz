import requests

url = "http://localhost:11434/api/generate"

response = requests.post(url, json={
    "model": "qwen2.5:7b-instruct",
    "prompt": "Напиши короткое описание LLM",
    "stream": False
})

print(response.json()["response"])