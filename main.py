from app import create_app

import uvicorn

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="192.168.50.200", port=8000)