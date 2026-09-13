from fastapi import FastAPI

app = FastAPI(title="Contract Intelligence API")

@app.get("/")
def home():
    return {
        "message": "Contract Intelligence API is running"
    }