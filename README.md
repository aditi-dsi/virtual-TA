# Virtual Teaching Assistant (TA) for TDS Course @ IIT Madras

This project is an AI-powered virtual assistant designed to help students of the **Tools in Data Science (TDS)** course at **IIT Madras**. It leverages a **RAG (Retrieval-Augmented Generation)** pipeline with multimodal capabilities to answer student queries using course materials, Discourse discussions, and image-based content.

---

## Features

- 🔍 **Qdrant** vector DB for vector stores and retrieval.
- 🌐 Playwright and Beautiful Soup for automated web scraping.
- 🧠 LLM responses powered by **Mistral's `Mistral Large`** model.
- 🖼️ Multimodal support: image + text query processing using **Mistral OCR**.
- 📎 Source-aware answers with extracted source citation links for transparency.
- 📊 Evaluation using `promptfoo` to benchmark answer accuracy.

---

## Local Installation

1. Clone the repo
   ```bash
   git clone https://github.com/aditi-dsi/virtual-ta.git
   cd virtual-ta

2. Install dependencies

    ```bash
    pip install -r requirements.txt
    ```

3. Set environment variables

    Create a .env file:
    ```bash
    MISTRAL_API_KEY=your_key
    QDRANT_CLIENT_URL=your_qdrant_host_url
    ```

4. Run the embedding pipeline

    ```bash
    cd pipelines
    python data_embedding_pipeline.py
    ```

5. Start the FastAPI server
    ```bash
    uvicorn app.main:app --reload
    ```

## Evaluation
Make sure to replace provider URL in `project-tds-virtual-ta-promptfoo.yaml` with your api endpoint (local/prod) before running the eval script.

Run evaluations using `promptfoo`:

    ```
    npx -y promptfoo eval --config project-tds-virtual-ta-promptfoo.yaml
    ```

## Deployment

The backend API is deployed on [Modal Labs](https://modal.com/). 

## License
MIT © 2025 Aditi Bindal
