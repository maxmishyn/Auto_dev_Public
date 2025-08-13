# Auto-Description Service

This service generates product descriptions for car listings using OpenAI Vision and Translation APIs.

## Getting Started

### Prerequisites

- Python 3.11+
- pip (Python package installer)
- Docker (optional, for containerized deployment)

### Installation

1.  **Clone the repository:**

    ```bash
    git clone <repository_url>
    cd Auto_dev_2
    ```

2.  **Create a virtual environment and activate it:**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

### Configuration

Create a `.env` file in the root directory of the project based on `.env.example` and fill in your API keys and other configurations:

```ini
OPENAI_API_KEY="your_openai_api_key_here"
SHARED_KEY="your_shared_secret_key_here"
VISION_MODEL="o4-mini"
TRANSLATE_MODEL="gpt-4.1-mini"
```

### Running the Service (Synchronous MVP)

To run the service locally for synchronous processing (single lot requests):

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag is useful for development as it reloads the server on code changes.

### Testing the Synchronous Endpoint

You can test the `/api/v1/generate-descriptions` endpoint with a single lot using `curl`.

**Example cURL Request:**

```bash
curl -X POST http://localhost:8000/api/v1/generate-descriptions \
-H "Content-Type: application/json" \
-d '{
    "signature": "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3",
    "version": "1.0.0",
    "languages": [
        "en",
        "ru"
    ],
    "lots": [
        {
            "webhook": "https://sample.plc.xx/api/sample_hook",
            "lot_id": "11-12345",
            "additional_info": "A red sports car with minor dents on the front bumper.",
            "images": [
                {
                    "url": "https://example.com/image1.jpg"
                }
            ]
        }
    ]
}'
```

**Note:** The `signature` in the example above is a placeholder. You will need to generate a valid HMAC-SHA256 signature based on your `SHARED_KEY` and the `lots` data.

### Health Check

To check the health of the service:

```bash
curl http://localhost:8000/health
```

This will return `{"status": "ok"}` if the service is running.

### Important Note on Asynchronous/Batch Mode

Currently, the asynchronous and batch processing modes are not fully utilized or documented for external use in this MVP. This documentation focuses on the synchronous (single lot) functionality.
