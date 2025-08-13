import asyncio

async def backoff(attempt: int):
    delay = 2 ** attempt
    await asyncio.sleep(delay)

def parse_response_output(response: dict) -> str:
    """
    Safely extracts the text content from the API response.
    Handles both Chat Completions format and the legacy format.
    """
    if not response:
        return ""

    # Handle Chat Completions format
    if 'choices' in response and response['choices']:
        message = response['choices'][0].get('message', {})
        if message and 'content' in message:
            return message['content']

    # Handle legacy format
    if 'output' in response:
        for item in response.get('output', []):
            if item.get('type') == 'message':
                if item.get('content') and isinstance(item['content'], list) and len(item['content']) > 0:
                    return item['content'][0].get('text', '')

    return ""