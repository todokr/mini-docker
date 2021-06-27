import json
import os
import shutil
import tarfile
from typing import Iterable

import requests

import commands.colors as colors

REGISTRY_BASE = 'https://registry-1.docker.io/v2'
IMAGES_DIR = '/var/opt/app/images'


def _fetch_auth_token(library: str, image: str) -> str:
    token_url = f'https://auth.docker.io/token?service=registry.docker.io&scope=repository:{library}/{image}:pull'
    token_response = requests.get(token_url)
    token_response.raise_for_status()
    return token_response.json()['token']


def _fetch_manifest(library: str, image: str, tag: str, token: str) -> dict:
    print(f'Fetching manifest for {image}:{tag}')
    manifest_url = f'{REGISTRY_BASE}/{library}/{image}/manifests/{tag}'
    headers = {'Authorization': f'Bearer {token}'}
    manifest_response = requests.get(manifest_url, headers=headers)
    manifest_response.raise_for_status()
    return manifest_response.json()


def _fetch_layer(library: str, image: str, layer_digest: str, token: str) -> Iterable[bytes]:
    print(f'Fetching layer: {layer_digest}')
    layer_url = f'{REGISTRY_BASE}/{library}/{image}/blobs/{layer_digest}'
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(layer_url, stream=True, headers=headers)
    response.raise_for_status()
    for chunk in response.iter_content(chunk_size=1024 * 8):
        if chunk:
            yield chunk


def run_pull(image: str, tag: str):
    print(f'Pulling {image}:{tag} ...')
    library = 'library'

    # Docker Hub からアクセストークンを取得
    # See also: https://docs.docker.com/registry/spec/auth/jwt/
    token = _fetch_auth_token(library, image)

    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR)

    # 指定した Docker image のマニフェストを取得して保存
    # See also: https://docs.docker.com/registry/spec/manifest-v2-2/
    manifest = _fetch_manifest(library, image, tag, token)

    image_name = f"{manifest['name'].replace('/', '_')}_{manifest['tag']}"
    image_base_dir = os.path.join(IMAGES_DIR, image_name)
    if os.path.exists(image_base_dir):
        shutil.rmtree(image_base_dir)
    manifest_json_name = f'{image_name}.json'

    with open(os.path.join(IMAGES_DIR, manifest_json_name), 'w') as manifest_json:
        manifest_json.write(json.dumps(
            manifest, ensure_ascii=False, indent=2, sort_keys=True, separators=(',', ': ')))

    # Docker image を構成する各イメージ・レイヤを取得して保存
    # See also: https://qiita.com/zembutsu/items/24558f9d0d254e33088f
    layer_digests = [layer['blobSum'] for layer in manifest['fsLayers']]
    image_layers_path = os.path.join(image_base_dir, 'layers')
    contents_path = os.path.join(image_layers_path, 'contents')
    if not os.path.exists(contents_path):
        os.makedirs(contents_path)

    for digest in layer_digests:
        layer_tar_name = f'{os.path.join(image_layers_path, digest)}.tar'
        with open(layer_tar_name, 'wb') as tar:
            for chunk in _fetch_layer(library, image, digest, token):
                if chunk:
                    tar.write(chunk)
        with tarfile.open(layer_tar_name, 'r') as tar:
            tar.extractall(str(contents_path))

    print(f'👌 {colors.GREEN}Docker image {image}:{tag} has been stored in {image_base_dir}{colors.END}')
