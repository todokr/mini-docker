from dataclasses import dataclass
import json
import re
import sys
import tarfile
from typing import Iterable
import requests

REGISTRY_BASE = 'https://registry-1.docker.io/v2'

def _fetch_auth_token(library: str, image: str) -> str:
    token_url = f'https://auth.docker.io/token?service=registry.docker.io&scope=repository:{library}/{image}:pull'
    token_response = requests.get(token_url)
    token_response.raise_for_status()
    return token_response.json()['token']

def _fetch_manifest(library: str, image: str, tag: str):
    print(f'Fetching manifest. image: {image}, tag: {tag}')
    manifest_url = f'{REGISTRY_BASE}/{library}/{image}/manifests/{tag}'
    token = _fetch_auth_token(library, image)
    headers = {'Authorization': f'Bearer {token}'}
    print(headers)
    manifest_response = requests.get(manifest_url, headers)
    manifest_response.raise_for_status()
    return manifest.json()

def run_pull():
    print('not implemented yet!')
    library = 'library'
    image = 'busybox'
    tag = 'latest'
    manifest = _fetch_manifest(library, image, tag)
    print(manifest)
    

    