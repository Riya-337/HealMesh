import os
import hvac
import logging

logger = logging.getLogger(__name__)

def get_secret(key: str, default: str = "") -> str:
    """
    Fetch a secret. Prefers Vault if VAULT_ADDR is set, 
    otherwise falls back to environment variables.
    """
    vault_addr = os.environ.get("VAULT_ADDR")
    vault_token = os.environ.get("VAULT_TOKEN")
    
    if vault_addr and vault_token:
        try:
            client = hvac.Client(url=vault_addr, token=vault_token)
            if client.is_authenticated():
                read_response = client.secrets.kv.v2.read_secret_version(path='healmesh')
                secrets = read_response['data']['data']
                if key in secrets and secrets[key] and secrets[key] != f"placeholder_{key.lower()}":
                    return secrets[key]
        except Exception as e:
            logger.warning(f"Failed to read from Vault for {key}: {e}")
            
    # Fallback to os.environ for tests or simple dev
    return os.environ.get(key, default)
