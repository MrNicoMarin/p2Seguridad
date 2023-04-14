#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
from threading import Lock
from collections import defaultdict
import shutil
import argparse
import uuid
import zlib
import time 
from bottle import route, run, request, error, response, HTTPError, static_file
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet
import json
from kms import KMS
import base64

storage_path: Path = Path(__file__).parent / "storage"
chunk_path: Path = Path(__file__).parent / "chunk"
project_path: Path = Path(__file__).parent

allow_downloads = True
dropzone_cdn = "https://cdnjs.cloudflare.com/ajax/libs/dropzone"
dropzone_version = "5.7.6"
dropzone_timeout = "120000"
dropzone_max_file_size = "100000"
dropzone_chunk_size = "1000000"
dropzone_parallel_chunks = "true"
dropzone_force_chunking = "true"

lock = Lock()
chucks = defaultdict(list)

chunks_json = []
file_json = []
first_upload = True 
kms = None
metadata = []

@error(500)
def handle_500(error_message):
    response.status = 500
    response.body = f"Error: {error_message}"
    return response


@route("/")
def index():
    index_file = Path(__file__) / "index.html"
    if index_file.exists():
        return index_file.read_text()
    return f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <link rel="stylesheet" href="{dropzone_cdn.rstrip('/')}/{dropzone_version}/min/dropzone.min.css"/>
    <link rel="stylesheet" href="{dropzone_cdn.rstrip('/')}/{dropzone_version}/min/basic.min.css"/>
    <script type="application/javascript"
        src="{dropzone_cdn.rstrip('/')}/{dropzone_version}/min/dropzone.min.js">
    </script>
    <title>pyfiledrop</title>
</head>
<body>

    <div id="content" style="width: 800px; margin: 0 auto;">
        <h2>Upload new files</h2>
        <form method="POST" action='/upload' class="dropzone dz-clickable" id="dropper" enctype="multipart/form-data">
        </form>

        <h2>
            Uploaded
            <input type="button" value="Clear" onclick="clearCookies()" />
        </h2>
        <div id="uploaded">

        </div>

        <script type="application/javascript">
            function clearCookies() {{
                document.cookie = "files=; Max-Age=0";
                document.getElementById("uploaded").innerHTML = "";
            }}

            function getFilesFromCookie() {{
                try {{ return document.cookie.split("=", 2)[1].split("||");}} catch (error) {{ return []; }}
            }}

            function saveCookie(new_file) {{
                    let all_files = getFilesFromCookie();
                    all_files.push(new_file);
                    document.cookie = `files=${{all_files.join("||")}}`;
            }}

            function generateLink(combo){{
                const uuid = combo.split('|^^|')[0];
                const name = combo.split('|^^|')[1];
                if ({'true' if allow_downloads else 'false'}) {{
                    return `<a href="/download/${{uuid}}" download="${{name}}">${{name}}</a>`;
                }}
                return name;
            }}


            function init() {{

                Dropzone.options.dropper = {{
                    paramName: 'file',
                    chunking: true,
                    forceChunking: {dropzone_force_chunking},
                    url: '/upload',
                    retryChunks: false,
                    parallelChunkUploads: {dropzone_parallel_chunks},
                    timeout: {dropzone_timeout}, // microseconds
                    maxFilesize: {dropzone_max_file_size}, // megabytes
                    chunkSize: {dropzone_chunk_size}, // bytes
                    init: function () {{
                        this.on("complete", function (file) {{
                            let combo = `${{file.upload.uuid}}|^^|${{file.upload.filename}}`;
                            saveCookie(combo);
                            document.getElementById("uploaded").innerHTML += generateLink(combo)  + "<br />";
                        }});
                    }}
                }}

                if (typeof document.cookie !== 'undefined' ) {{
                    let content = "";
                     getFilesFromCookie().forEach(function (combo) {{
                        content += generateLink(combo) + "<br />";
                    }});

                    document.getElementById("uploaded").innerHTML = content;
                }}
            }}

            init();

        </script>
    </div>
</body>
</html>
    """

@route("/upload", method="POST")
def upload():
    
    key, crypted_dek = kms.create_new_dek("P2Seguridad-GrupoD-KEKforDEK-ServerSide")

    global first_upload
    global chunks_json

    if first_upload:
        chunks_json = []
        first_upload = False

    file = request.files.get("file")
    if not file:
        raise HTTPError(status=400, body="No file provided")

    
    # key = Fernet.generate_key()
    # response = kms_v1.encrypt(
    #     KeyId=plain_dek,
    #     Plaintext=plaintext
    # )
    fernet = Fernet(key)
    chunk_data = file.file.read()
    encrypted_chunk = fernet.encrypt(chunk_data)

    chunk_info = {
        "index": int(request.forms["dzchunkindex"]),
        "key": base64.b64encode(crypted_dek).decode('utf-8'), 
    }

    chunks_json.append(chunk_info)
    
    dz_uuid = request.forms.get("dzuuid")

    if not dz_uuid:
        # Assume this file has not been chunked
        with open(storage_path / f"{uuid.uuid4()}_{secure_filename(file.filename)}", "wb") as f:
            file.save(f)
        return "File Saved"

    # Chunked download
    try:
        current_chunk = int(request.forms["dzchunkindex"])
        total_chunks = int(request.forms["dztotalchunkcount"])
    except KeyError as err:
        raise HTTPError(status=400, body=f"Not all required fields supplied, missing {err}")
    except ValueError:
        raise HTTPError(status=400, body=f"Values provided were not in expected format")

    save_dir = chunk_path / dz_uuid

    if not save_dir.exists():
        save_dir.mkdir(exist_ok=True, parents=True)

    # Save the individual chunk
    with open(save_dir / str(request.forms["dzchunkindex"]), "wb") as f:
        f.write(encrypted_chunk)

    # See if we have all the chunks downloaded
    with lock:
        chucks[dz_uuid].append(current_chunk)
        completed = len(chucks[dz_uuid]) == total_chunks

    # Concat all the files into the final file when all are downloaded
    if completed:
        first_upload = True
        
        file_info = {
            "file_name" : f"{dz_uuid}_{secure_filename(file.filename)}",
            "file_id" : dz_uuid,
            "chunks" : chunks_json
        }
        print(dz_uuid)
        file_json.append(file_info)

        metadata = json.dumps(file_json, indent=4)
        with open(project_path / f"metadata.json", "wb") as f:
            f.write(metadata.encode('utf-8'))

        print(f"{file.filename} has been uploaded")
        # shutil.rmtree(save_dir)

    return "Chunk upload successful"

@route("/download/<dz_uuid>")
def download(dz_uuid):
    if not allow_downloads:
        raise HTTPError(status=403)
    
    with open(project_path / f"metadata.json", "rb") as f:
        data = json.load(f)

    chunks_metadata = []
    file_name = ""
    for data_item in data:
        if data_item["file_id"] == dz_uuid:
            file_name = data_item["file_name"]
            for chunk_item in data_item["chunks"]:
                chunks_metadata.append(chunk_item)

    decrypted_chunks = []
    chunks_metadata.sort(key=lambda x: x["index"])

    for item in chunks_metadata:
        index = item["index"]
        with open(chunk_path / dz_uuid / f"{index}", "rb") as f:
            crypted_key = item["key"]
            key = kms.decrypt_dek("P2Seguridad-GrupoD-KEKforDEK-ServerSide", base64.b64decode(crypted_key.encode('utf-8')))
            fernet = Fernet(key)
            encrypted_chunk = (chunk_path / dz_uuid / f"{index}").read_bytes()
            decrypted = fernet.decrypt(encrypted_chunk)
            decrypted_chunks.append(decrypted)
        
    with open(storage_path / f"{file_name}", "wb") as f:
        f.write(b"".join(decrypted_chunks))

    for file in storage_path.iterdir():
        if file.is_file() and file.name.startswith(dz_uuid):
            return static_file(file.name, root=file.parent.absolute(), download=False)
    return HTTPError(status=404)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=16273, required=False)
    parser.add_argument("--host", type=str, default="0.0.0.0", required=False)
    parser.add_argument("-s", "--storage", type=str, default=str(storage_path), required=False)
    parser.add_argument("-c", "--chunks", type=str, default=str(chunk_path), required=False)
    parser.add_argument(
        "--max-size",
        type=str,
        default=dropzone_max_file_size,
        help="Max file size (Mb)",
    )
    parser.add_argument(
        "--timeout",
        type=str,
        default=dropzone_timeout,
        help="Timeout (ms) for each chuck upload",
    )
    parser.add_argument("--chunk-size", type=str, default=dropzone_chunk_size, help="Chunk size (bytes)")
    parser.add_argument("--disable-parallel-chunks", required=False, default=False, action="store_true")
    parser.add_argument("--disable-force-chunking", required=False, default=False, action="store_true")
    parser.add_argument("-a", "--allow-downloads", required=False, default=False, action="store_true")
    parser.add_argument("--dz-cdn", type=str, default=None, required=False)
    parser.add_argument("--dz-version", type=str, default=None, required=False)
    return parser.parse_args()


if __name__ == "__main__":

    args = parse_args()
    storage_path = Path(args.storage)
    chunk_path = Path(args.chunks)
    dropzone_chunk_size = args.chunk_size
    dropzone_timeout = args.timeout
    dropzone_max_file_size = args.max_size
    try:
        if int(dropzone_timeout) < 1 or int(dropzone_chunk_size) < 1 or int(dropzone_max_file_size) < 1:
            raise Exception("Invalid dropzone option, make sure max-size, timeout, and chunk-size are all positive")
    except ValueError:
        raise Exception("Invalid dropzone option, make sure max-size, timeout, and chunk-size are all integers")

    kms = KMS()
    result = kms.create_new_kek("P2Seguridad-GrupoD-KEKforDEK-ServerSide")
    if result:
        print("KEK created")
    else:
        print("KEK already created")
    
    if args.dz_cdn:
        dropzone_cdn = args.dz_cdn
    if args.dz_version:
        dropzone_version = args.dz_version
    if args.disable_parallel_chunks:
        dropzone_parallel_chunks = "false"
    if args.disable_force_chunking:
        dropzone_force_chunking = "false"
    if args.allow_downloads:
        allow_downloads = True

    if not storage_path.exists():
        storage_path.mkdir(exist_ok=True)
    if not chunk_path.exists():
        chunk_path.mkdir(exist_ok=True)

    print(
        f"""Timeout: {int(dropzone_timeout) // 1000} seconds per chunk
Chunk Size: {int(dropzone_chunk_size) // 1024} Kb
Max File Size: {int(dropzone_max_file_size)} Mb
Force Chunking: {dropzone_force_chunking}
Parallel Chunks: {dropzone_parallel_chunks}
Storage Path: {storage_path.absolute()}
Chunk Path: {chunk_path.absolute()}
"""
    )
    run(server="paste", port=args.port, host=args.host)
