import json
import httpx
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel, HttpUrl

app = FastAPI()

class ParseRequest(BaseModel):
    user_id: str
    file_id: str
    github_url: HttpUrl

def setup_user_directories(user_id: str) -> dict:
    """Creates directory structure for a user and global files, returns the paths."""
    current_dir = Path(__file__).resolve().parent
    root_dir = current_dir.parent.parent
    
    # 1. Сначала создаем глобальную папку для всех файлов (CV)
    global_files_dir = root_dir / "data" / "files"
    global_files_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Затем создаем специфичные папки для пользователя
    user_dir = root_dir / "data" / "users" / f"{user_id}"
    links_dir = user_dir / "links"
    processed_dir = user_dir / "processed"
    
    links_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    return {
        "links": links_dir,
        "files": global_files_dir,  # Возвращаем глобальную папку
        "processed": processed_dir
    }

def save_profile_to_json(user_id: str, github_id: str, data: dict):
    """Saves the parsed dictionary to a JSON file named by GitHub ID in the user's links folder."""
    dirs = setup_user_directories(user_id)
    filepath = dirs["links"] / f"{github_id}.json"
    
    with open(filepath, "w") as f:
        json.dump(data, f, indent=4)
    print(f"File {filepath} has been created.")

async def parse_github_task(user_id: str, profile_url: str):
    """Fetches data from GitHub API and triggers the save function."""
    # Extract username from URL (e.g., https://github.com/octocat)
    username = profile_url.rstrip("/").split("/")[-1]
    api_url = f"https://api.github.com/users/{username}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(api_url)
            if response.status_code == 200:
                profile_data = response.json()
                github_id = str(profile_data.get("id", username))
                save_profile_to_json(user_id, github_id, profile_data)
            else:
                save_profile_to_json(user_id, f"error_{username}", {"error": "User not found", "status": response.status_code})
        except Exception as e:
            save_profile_to_json(user_id, f"error_{username}", {"error": str(e)})

async def parse_file_task(user_id: str, file_id: str):

    dirs = setup_user_directories(user_id)
    pdf_path = dirs["files"] / f"{file_id}.pdf"
    processed_path = dirs["processed"] / f"processed_{file_id}.json"

    mock_data = {
        "status": "pending_llm_integration",
        "file_id": file_id
    }

    with open(processed_path, "w") as f:
        json.dump(mock_data, f, indent=4)

@app.post("/parse")
async def start_parsing(request: ParseRequest, background_tasks: BackgroundTasks):
    dirs = setup_user_directories(request.user_id)
    files_dir = dirs["files"]
    
    # Error handling для файла
    if request.file_id:
        pdf_path = files_dir / f"{request.file_id}.pdf"
        if not pdf_path.exists():
            return {"error": f"File {request.file_id}.pdf not found in data/files"}

    # Запускаем парсинг GitHub
    if request.github_url:
        background_tasks.add_task(parse_github_task, request.user_id, str(request.github_url))

    # Запускаем парсинг CV (будущая функция)
    if request.file_id:
        background_tasks.add_task(parse_file_task, request.user_id, request.file_id)

    # Return immediately
    return { 
        "status": "processing", 
        "user_id": request.user_id,
        "file_id": request.file_id
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)