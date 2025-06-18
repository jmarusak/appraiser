from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(
    title="Appraiser API",
    description="API to estimate the value of a item based on image and text",
)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
