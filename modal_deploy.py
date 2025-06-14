from modal import Image, asgi_app, App, Secret

app = App("virtual-ta-server")

image = Image.debian_slim().pip_install(
    "fastapi[all]",
    "uvicorn",
    "beautifulsoup4",
    "markdownify",
    "fastapi[standard]",
    "mistralai",
    "playwright",
    "pydantic",
    "tenacity",
    "qdrant-client"
)

image = image.add_local_python_source("app")

@app.function(image=image, secrets=[Secret.from_name("SECRET")])
@asgi_app()
def fastapi_app():
    import sys
    sys.path.append("/root")
    from app.main import app
    return app

if __name__ == "__main__":
    app.serve()