import aiohttp
import asyncio
import base64
import os
from typing import Union
from fastapi import UploadFile, HTTPException

VALID_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}

async def normalize_image_input(image_input: Union[str, UploadFile]) -> str:
    try:
        if isinstance(image_input, UploadFile):
            content = await image_input.read()
            mime_type = image_input.content_type
            if mime_type not in VALID_IMAGE_MIME_TYPES:
                raise HTTPException(status_code=400, detail="Unsupported file type")
            return base64.b64encode(content).decode()

        elif isinstance(image_input, str):
            if image_input.startswith("http://") or image_input.startswith("https://"):
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_input) as resp:
                        if resp.status != 200:
                            raise HTTPException(status_code=400, detail="Unable to fetch image URL")
                        content = await resp.read()
                        mime_type = resp.headers.get("Content-Type", "")
                        if mime_type not in VALID_IMAGE_MIME_TYPES:
                            raise HTTPException(status_code=400, detail="URL is not a supported image type")
                        return base64.b64encode(content).decode()

            elif os.path.exists(image_input):
                with open(image_input, "rb") as f:
                    return base64.b64encode(f.read()).decode()

            else:
                try:
                    base64.b64decode(image_input)
                    return image_input
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid base64 image input")

        raise HTTPException(status_code=400, detail="Invalid image input format")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image processing failed: {str(e)}")


if __name__ == "__main__":
    test_path = "./test.png"
    print("Absolute path:", os.path.abspath(test_path))
    print("Exists:", os.path.exists(test_path))
    print("Is file:", os.path.isfile(test_path))
    
    result = asyncio.run(normalize_image_input(test_path))
    print("Result:", result[:100], "...")