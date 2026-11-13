from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "online", "message": "Container DevOps/SRE rodando com sucesso no WSL2!"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
