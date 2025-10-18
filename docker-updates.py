import subprocess
import requests
import logging
from pathlib import Path

# === Logging Setup ===
log_file = Path(__file__).with_name("docker_updates.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, mode='w', encoding='utf-8'),
        # logging.StreamHandler()  
    ]
)
logger = logging.getLogger(__name__)

def get_local_images():
    """Return list of (repository, tag, digest) for local images."""
    result = subprocess.run(
        ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
        capture_output=True, text=True, check=True
    )
    images = []
    for line in result.stdout.strip().splitlines():
        if "<none>" in line:
            continue
        repo_tag = line.strip()
        try:
            inspect = subprocess.run(
                ["docker", "inspect", "--format", "{{.RepoDigests}}", repo_tag],
                capture_output=True, text=True, check=True
            )
            digest_list = inspect.stdout.strip().strip("[]")
            digest = digest_list.split("@")[1] if "@" in digest_list else None
        except subprocess.CalledProcessError:
            digest = None
        images.append((repo_tag, digest))
    return images


def get_auth_token(repo):
    """Fetch auth token for Docker Hub repo."""
    repo_name = repo if "/" in repo else f"library/{repo}"
    auth_url = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repo_name}:pull"
    r = requests.get(auth_url)
    if r.status_code == 200:
        return r.json().get("token")
    logger.warning(f"Failed to get auth token for {repo_name}: {r.status_code}")
    return None


def get_remote_digest(repo_tag):
    """Return remote digest using Docker Registry API with auth."""
    if ":" not in repo_tag:
        repo_tag += ":latest"
    repo, tag = repo_tag.split(":", 1)
    if "/" not in repo:
        repo = f"library/{repo}"
    base = "https://registry-1.docker.io"
    url = f"{base}/v2/{repo}/manifests/{tag}"
    headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
    
    token = get_auth_token(repo)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    logger.info(f"Fetching remote digest for {repo_tag} from {url}")
    resp = requests.get(url, headers=headers)
    logger.info(f"Response: {resp.status_code}")
    if resp.status_code == 200:
        digest = resp.headers.get("Docker-Content-Digest")
        logger.info(f"Remote digest for {repo_tag}: {digest}")
        return digest
    else:
        logger.warning(f"Failed to get digest for {repo_tag}: {resp.text[:200]}")
        return None


def check_updates():
    images = get_local_images()
    logger.info(f"Found {len(images)} local images.")
    print(f"Found {len(images)} local images.")
    for repo_tag, local_digest in images:
        remote_digest = get_remote_digest(repo_tag)
        if not remote_digest:
            print(f"{repo_tag}: ❌ unable to fetch remote digest")
            continue
        if local_digest and remote_digest == local_digest:
            print(f"{repo_tag}: ✅ up to date")
        else:
            print(f"{repo_tag}: ⚠️ update available")


if __name__ == "__main__":
    logger.info("=== Docker Image Update Check Started ===")
    check_updates()
    logger.info("=== Docker Image Update Check Finished ===")
    logger.info(f"Log saved to: {log_file}")
