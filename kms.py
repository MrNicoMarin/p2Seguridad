from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from google.cloud import kms_v1, storage 
import os
import argparse

class KMS():

    def __init__(self):

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "master-security-381510-d6623692c67a.json"
        self.client = kms_v1.KeyManagementServiceClient()
        self.project_id = "master-security-381510"
        self.location_id = "europe-southwest1"
        self.keyring_id = "kek"

        try:
            self.client.get_key_ring(name=self.client.key_ring_path(self.project_id, self.location_id, self.keyring_id))
            print("Keyring exists")
        except Exception as e:
            location_name = f"projects/{self.project_id}/locations/{self.location_id}"
            self.client.create_key_ring(parent=location_name, key_ring_id=self.keyring_id)
            print("Keyring created")
            
    def list_keyrings(self) -> list:
        location_name = f"projects/{self.project_id}/locations/{self.location_id}"
        keyrings = self.client.list_key_rings(parent=location_name)
        return [keyring.name for keyring in keyrings]

    # When a new user is create, we create a new key (KEK) for him 
    def create_new_kek(self, kek_id : str) -> bool:
        try:
            keyring_name = self.client.key_ring_path(self.project_id, self.location_id, self.keyring_id)
            self.client.create_crypto_key(parent=keyring_name, crypto_key_id=kek_id, crypto_key={"purpose": kms_v1.CryptoKey.CryptoKeyPurpose.ENCRYPT_DECRYPT})
            return True
        except:
            return False
        
    def create_new_dek(self, kek_id : str) -> tuple:
        plain_key = AESGCM.generate_key(bit_length=256)

        kek_name = f"projects/{self.project_id}/locations/{self.location_id}/keyRings/{self.keyring_id}/cryptoKeys/{kek_id}"
        encrypt_response = self.client.encrypt(name=kek_name, plaintext=plain_key)
        encrypted_key = encrypt_response.ciphertext
        
        return plain_key, encrypted_key
    
    def decrypt_dek(self, kek_id : str, encrypted_key : bytes) -> bytes:
        kek_name = f"projects/{self.project_id}/locations/{self.location_id}/keyRings/{self.keyring_id}/cryptoKeys/{kek_id}"
        decrypt_response = self.client.decrypt(name=kek_name, ciphertext=encrypted_key)
        decrypted_key = decrypt_response.plaintext
        return decrypted_key
        


""" How to use 
kms = KMS()
kms.list_keyrings()

result = kms.create_new_kek("nico_test")

if result:
    print("kek created")
else:
    print("kek already created")

plain_dek,crypted_kek = kms.create_new_dek("nico_test")

print("KEK: ", plain_dek)

decrypted_dek = kms.decrypt_dek("nico_test", crypted_kek)

print("Decrypted KEK", decrypted_dek)
"""


# Upload files to the Google Cloud Storage bucket
class GCS():
    def __init__(self, bucket_name):
        self.bucket_name = bucket_name
        self.storage_client = storage.Client()

    def upload_file(self, source_file_path):
        # Extract the filename and create a folder with the same name
        filename = os.path.basename(source_file_path)
        folder_name = os.path.splitext(filename)[0]
        folder_blob = self.bucket_name.blob(folder_name)
        folder_blob.upload_from_string('')

        # Upload the file to the created folder
        folder_path = f'{folder_name}/{filename}'
        blob = self.storage_client.bucket(self.bucket_name).blob(folder_path)
        blob.upload_from_filename(source_file_path)

        print(f"File {source_file_path} uploaded to {folder_path} in bucket {self.bucket_name}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Manage files in Google Cloud Storage.')
    subparsers = parser.add_subparsers(title='commands', dest='command', help='Available commands')

    # Create the parser for the "upload" command
    upload_parser = subparsers.add_parser('upload', help='Upload a file to Google Cloud Storage.')
    upload_parser.add_argument('file_path', type=str, help='The path to the file to upload.')
    upload_parser.add_argument('--bucket', type=str, default='my-bucket', help='The name of the Google Cloud Storage bucket to use.')
    upload_parser.add_argument('--encryption', choices=['none', 'CSE', 'SSE'], default='none', help='Encryption mode')

    # Parse the arguments
    args = parser.parse_args()

    if args.command == 'upload':
        gcs = GCS(args.bucket)

        # Determine encryption mode
        if args.encryption == 'CSE':
            encryption_key = input('Enter encryption key: ')
            gcs.upload_file_cse(args.file_path, args.file_path, encryption_key)
        else:
            gcs.upload_file(args.file_path, args.file_path)