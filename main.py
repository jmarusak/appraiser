import os
import base64
import logging
import datetime

from dotenv import load_dotenv
from mimetypes import guess_type

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from google import genai
from google.genai.types import GenerateContentConfig, GoogleSearch, Part, Tool
from google.cloud import storage

logging.basicConfig(level=logging.INFO)

load_dotenv()

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_REGION")
MODEL_ID = os.environ.get("GOOGLE_CLOUD_MODEL_ID")
STORAGE_BUCKET = os.environ.get("GOOGLE_CLOUD_STORAGE_BUCKET")

storage_client = storage.Client(project=PROJECT_ID)
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

class ValuationRequest(BaseModel):
    description: str 
    image_uri: str
    image_data: str
    content_type: str

class ValuationResponse(BaseModel):
    estimated_value: float
    product_name: str
    product_description: str
    search_urls: list[str]

app = FastAPI(
    title="Appraiser API",
    description="API to estimate the value of a item based on image and text",
)

with open("prompt_valuation.md", "r") as file:
    prompt_valuation_template = file.read()

with open("prompt_parsing.md", "r") as file:
    prompt_parsing_template = file.read()

def get_image_data(file: UploadFile, contents: bytes) -> str:
    """Creates a data URL for the image."""
    encoded_image = base64.b64encode(contents).decode("utf-8")
    return f"data:{file.content_type};base64,{encoded_image}"

def upload_image_to_gcs(file: UploadFile) -> str:
    """Uploads an image file to Google Cloud Storage and returns the GCS URI."""
    bucket = storage_client.bucket(STORAGE_BUCKET)
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    blob = bucket.blob(filename)

    try:
        blob.upload_from_file(file.file, content_type=file.content_type)
        return f"gs://{STORAGE_BUCKET}/{filename}"
    except Exception as e:
        logging.error(f"Error uploading image to Cloud Storage: {e}")
        raise

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
        image_uri = upload_image_to_gcs(image_file) if STORAGE_BUCKET else None
        image_data = get_image_data(image_file, contents)

        return JSONResponse(
            {
                "image_data": image_data,
                "image_uri": image_uri,
                "content_type": image_file.content_type,
            }
        )
    except Exception as e:
        logging.error(f"Error uploading image: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading image: {e}")

def appraise_value(request: ValuationRequest) -> ValuationResponse:
    """
    Calls Gemini API with Search Tool to estimate item value, then parses the result into a ValuationResponse.
    """

    currency = "CAD"

    prompt_valuation = (
        prompt_valuation_template 
        .replace("{{description}}", request.description)
        .replace("{{currency}}", currency)
    )

    print(f"Valuation prompt: {prompt_valuation}")

    google_search_tool = Tool(google_search=GoogleSearch())
    config_with_search = GenerateContentConfig(tools=[google_search_tool])

    image_uri = request.image_uri
    image_data = base64.b64decode(request.image_data.split(",", 1)[1]) if request.image_data else None 
    mime_type = request.content_type

    config_with_search = None

    if image_data:
        response_with_search = client.models.generate_content(
            model=MODEL_ID,
            contents=[
                Part.from_bytes(data=image_data, mime_type=mime_type),
                prompt_valuation,
            ],
            config=config_with_search,
        )
    elif image_uri:
        response_with_search = client.models.generate_content(
            model=MODEL_ID,
            contents=[
                Part.from_uri(file_uri=image_uri, mime_type=guess_type(image_uri)[0]),
                prompt_valuation,
            ],
            config=config_with_search,
        )
    else:
        raise ValueError("Must provide image_uri")

    # Use final part of search results with answer
    valuation_text = "Error estimating value: no text response."
    for part in response_with_search.candidates[0].content.parts:
        if part.text:
            valuation_text = part.text

    # Second Gemini call to parse the valuation string into a ValuationResponse
    config_for_parsing = GenerateContentConfig(
        response_mime_type="application/json", response_schema=ValuationResponse
    )

    valuation_schema = f"{ValuationResponse.model_json_schema()}"

    prompt_parsing = (
        prompt_parsing_template
        .replace("{{valuation_text}}", valuation_text)
        .replace("{{valuation_schema}}", valuation_schema)
        .replace("{{currency}}", currency)
    )

    print(f"Parsing prompt: {prompt_parsing}")

    response_for_parsing = client.models.generate_content(
        model=MODEL_ID, contents=prompt_parsing, config=config_for_parsing
    )
    valuation_response = response_for_parsing.text

    return ValuationResponse.model_validate_json(valuation_response)

@app.post("/appraise", response_model=ValuationResponse)
async def appraise_item(request: ValuationRequest):
    if not request.image_uri and not request.image_data:
        raise HTTPException(
            status_code=400, detail="Either image_uri or image_data is required."
        )

    try:
        response_data = appraise_value(request)
        return JSONResponse(content=response_data.model_dump())
    except Exception as e:
        logging.error(f"Internal server error in /value: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {e}")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
