import base64
import logging

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)

class ValuationRequest(BaseModel):
    description: str 

class ValuationResponse(BaseModel):
    estimated_value: float
    reasoning: str
    search_urls: list[str]

app = FastAPI(
    title="Appraiser API",
    description="API to estimate the value of a item based on image and text",
)

def get_data_url(file: UploadFile, contents: bytes) -> str:
    """Creates a data URL for the image."""
    encoded_image = base64.b64encode(contents).decode("utf-8")
    return f"data:{file.content_type};base64,{encoded_image}"

@app.post("/upload-image")
async def upload_image(image_file: UploadFile = File(...)):
    """Uploads an image, returns a Data URL for preview, and stores the GCS URI."""
    if not image_file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, detail="Invalid image file type. Please upload an image."
        )

    try:
        contents = await image_file.read()
        await image_file.seek(0)  # Reset for GCS upload
        # Placeholder for GCS upload logic
        #image_uri = upload_image_to_gcs(image_file) if STORAGE_BUCKET else None
        image_uri = ""
        data_url = get_data_url(image_file, contents)

        return JSONResponse(
            {
                "data_url": data_url,
                "gcs_uri": image_uri,
                "content_type": image_file.content_type,
            }
        )
    except Exception as e:
        logging.error(f"Error uploading image: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading image: {e}")

@app.post("/appraise", response_model=ValuationResponse)
async def appraise_item(request: ValuationRequest):
    # Placeholder logic for valuation
    estimated_value = 100.0
    reasoning = request.description + " is estimated to be worth $100 based on current market trends."
    search_urls = [
        "https://example.com/search1",
        "https://example.com/search2",
        "https://example.com/search3"
    ]

    response = ValuationResponse(
        estimated_value=estimated_value,
        reasoning=reasoning,
        search_urls=search_urls
    )
    return JSONResponse(content=response.model_dump(), status_code=200)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
