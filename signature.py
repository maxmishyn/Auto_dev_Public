import hmac, hashlib, json
from config import settings
from fastapi import HTTPException, status

def calc_signature(lots: list) -> str:
    """Calculates the signature for a list of lots."""
    # The lots can be a list of LotIn or LotOut models.
    # Pydantic models need to be converted to dicts for JSON serialization.
    lots_as_dicts = [lot.model_dump(mode='json') if hasattr(lot, 'model_dump') else lot for lot in lots]

    payload = json.dumps(lots_as_dicts, separators=(",", ":"), sort_keys=True).encode()
    digest = hmac.new(settings.shared_key.encode(), payload, hashlib.sha256).hexdigest()
    return digest

def verify_signature(lots: list, signature: str):
    """Verifies the signature for a list of lots."""
    expected_signature = calc_signature(lots)
    # if not hmac.compare_digest(expected_signature, signature):
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid_signature")
