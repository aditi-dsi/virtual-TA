import os, re, logging, json
from mistralai import Mistral
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from qdrant_client import QdrantClient
from qdrant_client.models import SearchParams
from app.schemas import QueryRequest
from app.utils.image_normalizer import normalize_image_input

logger = logging.getLogger(__name__)

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
QDRANT_CLIENT_URL = os.getenv("QDRANT_CLIENT_URL", "http://localhost:6333")
mistral_client = Mistral(api_key=MISTRAL_API_KEY)
qdrant_client = QdrantClient(url=QDRANT_CLIENT_URL)
COLLECTION_NAME = "tds-embeddings"

LLM_MODEL = "mistral-large-latest"
OCR_MODEL = "mistral-ocr-latest"
EMBEDDING_MODEL = "mistral-embed"


# === VectorDB Health Check ===
def perform_health_check():
    try:
        count = qdrant_client.count(collection_name=COLLECTION_NAME, exact=True).count
        return {"status": "healthy", "message": "Hey, I am Virtual TA for TDS course! Make api calls to /query endpoint with your question and image attachment (optional) to get answers."}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
    

async def handle_query(request: QueryRequest):
    query_embedding = await process_multimodal_query(request.question, request.image)
    extracted_text_from_image = await extract_text_from_image(request.image) if request.image else ""
    relevant_chunks = search_similar_chunks(query_embedding)

    if not relevant_chunks:
        return {"answer": "No relevant results found.", "links": []}
    
    grouped_chunks = group_and_deduplicate_chunks(relevant_chunks)
    request.question += f"\n\nExtracted text from attached image:\n{extracted_text_from_image}" if extracted_text_from_image else ""
    llm_response = await generate_llm_answer(request.question, grouped_chunks)
    parsed = parse_llm_response(llm_response)

    if not parsed["links"]:
        parsed["links"] = fallback_links_from_chunks(relevant_chunks)

    return parsed


# === Embed Query ===
def embed_query(text: str):
    response = mistral_client.embeddings.create(
        model=EMBEDDING_MODEL,
        inputs=[text]
    )
    return response.data[0].embedding

def search_similar_chunks(embedding):
    hits = qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=embedding,
        search_params=SearchParams(hnsw_ef=128, exact=True),
        limit=3,
        with_payload=True,
        score_threshold=0.7,
    )
    return [hit.payload for hit in hits]


def group_and_deduplicate_chunks(chunks):
    grouped = {}
    for chunk in chunks:
        source = chunk.get("source")
        key = None
        if source == "discourse":
            key = f"discourse_{chunk.get('post_id')}"
        elif source == "course_material":
            key = f"course_{chunk.get('filename')}"
        else:
            key = f"generic_{chunk.get('url') or chunk.get('original_url')}"

        if key not in grouped:
            grouped[key] = []
        grouped[key].append(chunk)

    final_chunks = []
    for group in grouped.values():
        group.sort(key=lambda x: x.get("score", 0), reverse=True)
        final_chunks.extend(group[:3])

    final_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
    return final_chunks[:10]


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
)
def _call_ocr_api(base64_img: str):
    response = mistral_client.ocr.process(
        model=OCR_MODEL,
        document={
            "type": "image_url",
            "image_url": f"data:image/jpeg;base64,{base64_img}"
        },
        include_image_base64=True,
    )
    return response


# === Vision ===
async def extract_text_from_image(base64_img):
    try:
        result = _call_ocr_api(base64_img)
        extracted_text = "\n\n".join([page.markdown for page in result.pages])
        return extracted_text
    except Exception as e:
        logger.error(f"Vision API failed after retries: {e}")
        return ""


# === Process Multimodal Query ===
async def process_multimodal_query(text, image):
    if image:
        normalized_image = await normalize_image_input(image)
        if not normalized_image:
            raise ValueError("Invalid image input format or unable to process the image.")
        vision_text = await extract_text_from_image(normalized_image)
        text += f"\n{vision_text}"
    return embed_query(text)


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
)
def _call_llm_with_retry(prompt: str) -> str:
    response = mistral_client.chat.complete(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=700,
        timeout_ms=30000,
    )
    return response.choices[0].message.content.strip()


# === LLM ===
async def generate_llm_answer(question, docs):
    context = ""
    for result in docs:
        source_type = "Discourse post" if result.get("source") == "discourse" else "Course material"
        url = result.get("url") or result.get("original_url")
        context += f"\n\n{source_type} (URL: {url}):\n{result.get('text', result.get('content', ''))[:1500]}"

    prompt = f"""

    You are a senior TA for the Tools in Data Science course, your job is to provide 100% accurate information from the context with references to relevant sources. 
    Answer the following question based ONLY on the provided context. 
    Carefully read the complete provided discourse discussion or course material documentation step-by-step from top to botton and then find out the exact accurate answer to the question. 
    If context is neutral and doesn't provide a clear answer, think step-by-step and provide a one clear answer based on the discussion on the discourse posts or course material.
    If you cannot answer the question based on the context, say "I don't have enough information to answer this question."
    
    Context:
    {context}
    
    Question: {question}
    
    Read the complete discourse discussion and other context carefully and return your response in this exact format:
    A complete answer with two fields:
    <A comprehensive yet concise and to the point answer>
    <A "Sources:" section that must lists the URLs and relevant text snippets you used to answer>
    
    Sources must be in this exact format:
    Sources:
    1. URL: [exact_url_1], Text: [brief quote or description]
    2. URL: [exact_url_2], Text: [brief quote or description]
    
    Make sure the URLs are copied exactly from the context without any changes.
    """
    try:
        result = _call_llm_with_retry(prompt)
        return result
    except Exception as e:
        logger.error(f"LLM API failed after retries: {e}")
        return "The system is currently overloaded or encountered an error. Please try again."


def parse_llm_response(response):
    try:
        logger.info("Parsing LLM response")

        parts = response.split("Sources:", 1)
        if len(parts) == 1:
            for heading in ["Source:", "References:", "Reference:"]:
                if heading in response:
                    parts = response.split(heading, 1)
                    break

        answer = parts[0].strip()
        links = []

        if len(parts) > 1:
            sources_text = parts[1].strip()
            source_lines = sources_text.split("\n")

            for line in source_lines:
                line = line.strip()
                if not line:
                    continue
                line = re.sub(r'^\d+\.\s*', '', line)
                line = re.sub(r'^-\s*', '', line)

                url_match = re.search(r'URL:\s*\[(.*?)\]|url:\s*\[(.*?)\]|\[(http[^\]]+)\]|URL:\s*(http\S+)|url:\s*(http\S+)|(http\S+)', line, re.IGNORECASE)
                text_match = re.search(r'Text:\s*\[(.*?)\]|text:\s*\[(.*?)\]|[\"\"](.*?)[\"\"]|Text:\s*\"(.*?)\"|text:\s*\"(.*?)\"', line, re.IGNORECASE)

                if url_match:
                    url = next((g for g in url_match.groups() if g), "").strip()
                    text = "Source reference"
                    if text_match:
                        text_value = next((g for g in text_match.groups() if g), "")
                        if text_value:
                            text = text_value.strip()
                    if url and url.startswith("http"):
                        links.append({"url": url, "text": text})


        logger.info(f"Parsed answer (length: {len(answer)}) and {len(links)} sources")
        return {"answer": answer, "links": links}

    except Exception as e:
        logger.error(f"Error parsing LLM response: {e}")
        return {
            "answer": "Error parsing the response from the language model.",
            "links": []
        }


# === Fallback ===
def fallback_links_from_chunks(chunks):
    seen = set()
    links = []
    for chunk in chunks:
        url = chunk.get("url") or chunk.get("link") or chunk.get("original_url")
        if url and url not in seen:
            links.append({"url": url, "text": chunk.get("text", "")[:100] + "..."})
            seen.add(url)
    return links
