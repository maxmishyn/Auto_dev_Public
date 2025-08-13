# Test Client for Auto-Description Service

This test client is a FastAPI application that provides endpoints to test the main Auto-Description Service.

## Getting Started

### Prerequisites

- Python 3.11+
- pip (Python package installer)

### Installation

1.  **Navigate to the `test_client` directory:**

    ```bash
    cd test_client
    ```

2.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

### Configuration

Create a `.env` file in the `test_client` directory based on `.env.example` and fill in your `SHARED_KEY`:

```ini
SHARED_KEY="your_shared_secret_key_here"
```

**Note:** The `SHARED_KEY` must match the one used in the main Auto-Description Service.

### Running the Test Client

To run the test client:

```bash
uvicorn client:app --host 0.0.0.0 --port 8001 --reload
```

The test client will be available at `http://localhost:8001`.

### Endpoints

-   `POST /run-sync-test`: Sends a single lot to the main service and returns the response.
-   `POST /run-async-test`: Sends 10 lots to the main service and waits for the webhooks.
-   `POST /webhook`: An endpoint to receive webhooks from the main service.
