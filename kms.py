from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from google.cloud import kms_v1, storage 
import os
from os import environ, listdir
from kms import bucketName, localFolder, bucketFolder
from os.path import isfile, join

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



#Google Cloud Storage
class GCS():
    bucketName = environ.get('Bucket_Grupo_D')
    bucketFolder = environ.get('Folder_Grupo_D') # Folder for all subfolders with the files
    localFolder = environ.get('Local_Folder') # Folder for the data

    # Object representing our bucket
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucketName)

    # Upload files to GCS bucket
    def upload_files(bucket, bucketName):
        files = [f for f in listdir(localFolder) if isfile(join(localFolder, f))]
        for file in files: 
            fileName = localFolder + file
            blob = bucket.blob(bucketFolder + file) # Set the desired destination of each file
            blob.upload_from_filename(fileName)
        return f'Uploaded {files} to "{bucketFolder}" in "{bucketName}".'
    
    # Download files from GCS bucket
    def download_file(bucket, fileName):
        blob = bucket.blob(bucketFolder + fileName)
        if blob.exists():
            blob.download_to_filename(localFolder + fileName)
            return f'{fileName} downloaded from bucket.'
        else:
            return f'{fileName} does not exist in bucket.'

    # List files in GCS bucket lokalFile
    def list_files(bucket):
        files = bucket.list_blobs(prefix=bucketFolder)
        fileList = [file.name for file in files if '.' in file.name]
        return fileList
    
    
    print("Type device id:")
    input = int(input("Enter 'u' to upload a file, 'd' to download a file or 'l' to list all files"))

    if input == 'u':
        print(kms.upload_files(bucket, bucketName))

    if input == 'd':
        print(kms.download_file(bucket))

    elif input == 'l':
        print(kms.list_files(bucket))
