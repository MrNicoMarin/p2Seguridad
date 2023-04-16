import os
import random
import shutil
import sys
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import datetime
import json
from kms import KMS


class Client:

    def __init__(self):

        # Set the folder path for local file uploads
        self.desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        self.folder_path = os.path.join(self.desktop_path, "Uploads")

        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)

        # Instance of the KMS class
        self.kms = KMS()
        result = self.kms.create_new_kek("P2Seguridad-GrupoD-KEKforDEK-ClientSide")
        if result:
            print("KEK created")
        else:
            print("KEK already created")

    def modify_metadata(self,algorithm, file_path):
        try:
            with open(file_path + '.metadata.json', 'r') as f:
                metadata = json.load(f)  # Cargar el archivo JSON en una estructura de datos
        except FileNotFoundError:
            metadata = {}
            metadata['last_modification'] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        metadata['algorithm'] = algorithm  # Modificar el dato deseado en la estructura de datos
        with open(file_path + '.metadata.json', 'w') as f:
            json.dump(metadata, f, indent=4)

    # Encrypt the file using the KMS-encrypted Fernet key
    def encrypt(self, file_path):
        self.modify_metadata(0,file_path)
        with open(file_path, "rb") as f:
            data = f.read()
        
        # Encrypt the Fernet key with the KMS KEK
        plain_dek,crypted_kek = self.kms.create_new_dek("P2Seguridad-GrupoD-KEKforDEK-ClientSide")
        
        # Write the encrypted Fernet key to .key file
        with open(file_path + ".key", "wb") as f:
            f.write(crypted_kek)
        
        # Use the Fernet key to encrypt the file
        fernet = Fernet(plain_dek)
        encrypted = fernet.encrypt(data)
        
        with open(file_path, "wb") as f:
            f.write(encrypted)
    
    def encrypt_file_with_metadata(self, file_path):
    # Generate a new AES key for the file
        self.modify_metadata(1, file_path)
        with open(file_path + ".metadata.json", 'r') as metadata_file:
            metadata = json.load(metadata_file)

        aad = json.dumps(metadata).encode()
        nonce = os.urandom(12) # Generate a random 12-byte nonce
        plain_dek,crypted_key = self.kms.create_new_dek_aesgcm("P2Seguridad-GrupoD-KEKforDEK-ClientSide")
         # Write the encrypted AESGCM key to .key file
        with open(file_path + ".key", "wb") as f:
            f.write(crypted_key)

        # Read the contents of the file
        with open(file_path, 'rb') as file:
            plaintext = file.read()
        
        aesgcm = AESGCM(plain_dek)
        # Encrypt the file content with AEAD
        ciphertext = aesgcm.encrypt(nonce, plaintext, aad)

        # Write the encrypted file to disk
        with open(file_path , 'wb') as encrypted_file:
            encrypted_file.write(nonce + ciphertext)
        
        return file_path 


    # Decrypt the file using the KMS-encrypted Fernet key
    def decrypt(self, file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        
        # Read the KMS-encrypted Fernet key from .key file
        with open(file_path + ".key", "rb") as f:
            encrypted_key = f.read()
        
        # Decrypt the KMS-encrypted Fernet key
        decrypted_dek = self.kms.decrypt_dek("P2Seguridad-GrupoD-KEKforDEK-ClientSide", encrypted_key)
        
        # Use the decrypted Fernet key to decrypt the file
        fernet = Fernet(decrypted_dek)
        decrypted = fernet.decrypt(data)
        
        with open(file_path, "wb") as f:
            f.write(decrypted)


    # Función para desencriptar un archivo con metadatos y AEAD
    def decrypt_file_with_metadata(self, file_path):
        with open(file_path + ".metadata.json", 'r') as metadata_file:
            metadata = json.load(metadata_file)
        aad = json.dumps(metadata).encode()
        # Extract the nonce, aad, and ciphertext from the encrypted file
        with open(file_path, 'rb') as encrypted_file:
            nonce = encrypted_file.read(12)
            ciphertext = encrypted_file.read()
        # Read the encrypted AESGCM key from .key file
        with open(file_path + ".key", 'rb') as key_file:
            encrypted_key = key_file.read()
        
        # Decrypt the KMS-encrypted key
        plain_dek = self.kms.decrypt_dek("P2Seguridad-GrupoD-KEKforDEK-ClientSide", encrypted_key)
        # Create an AESGCM instance with the decrypted DEK
        aesgcm = AESGCM(plain_dek)

        # Decrypt the ciphertext to plaintext
        plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
        plaintext= plaintext.decode('utf-8')
        # Write the decrypted plaintext to a new file
        decrypted_file_path = file_path
        with open(decrypted_file_path, 'wb') as decrypted_file:
            decrypted_file.write(plaintext.encode('utf-8'))
        
        return decrypted_file_path


    def upload_file(self):
        filename = input("Enter the name of the file to upload (include file extension): ")

        # Create a subfolder with the same name as the file to upload
        subfolder_path = os.path.join(self.folder_path, os.path.splitext(filename)[0])
        if not os.path.exists(subfolder_path):
            os.makedirs(subfolder_path)

        # Construct the full path of the file to upload
        file_path = os.path.join(subfolder_path, filename)

        if os.path.exists(file_path):
            overwrite = input(f"'{filename}' already exists in the 'Uploads' folder. Do you want to overwrite it? (y/n): ")
            if overwrite.lower() == 'n':
                return print(f"'{filename}' has not been overwritten.")
        
        while True: 
            upload_path = input("Enter the path of the file to upload: ")
            if os.path.exists(upload_path):
                try:
                    # Copy the file to the subfolder
                    shutil.copy(upload_path, file_path)
                    # Encrypt the file before uploading
                    while True:
                        algorithm = input("Enter the algorithm to encrypt, 0 for Fernet or 1 AES+metadata: ")
                        if(algorithm=="0"):
                            self.encrypt(file_path)
                            print(f"\n{filename} has been successfully uploaded.")
                            break
                        elif(algorithm=="1"):
                            self.encrypt_file_with_metadata(file_path)
                            print(f"\n{filename} has been successfully uploaded encrypted with metadada.")
                            break
                        else:
                            print("Invalid algorithm. Please try again.")  
                    break  
                except shutil.Error as e:
                    print(f"Error uploading file: {e}")
            else:
                print("Invalid file path. Please try again.")


    def list_files(self):
        print("List of all uploaded files:")
        for root, _, files in os.walk(self.folder_path):
            for filename in files:
                if not filename.endswith('.key') and not filename.endswith('.metadata.json'):
                    print(f"- {filename}")


    def download_file(self):
        filename = input("Enter the name of the file to download (include file extension): ")

        for root, _, files in os.walk(self.folder_path):
            if filename in files:
                file_path = os.path.join(root, filename)
                # Look metadata
                with open(file_path + '.metadata.json', 'r') as f:
                    metadata = json.load(f)  # Load the JSON file into a data structure
                encryption = metadata['algorithm']
                # Decrypt file before downloading
                if(encryption==0):
                    self.decrypt(file_path)
                elif(encryption==1):
                    self.decrypt_file_with_metadata(file_path)
                download_path = os.path.join(os.path.expanduser("~"), "Downloads", filename)
                try:
                    shutil.copy(file_path, download_path)
                    print(f"\n{filename} has been successfully downloaded.")
                    if(encryption==0):
                        self.encrypt(file_path)
                    elif(encryption==1):
                        self.encrypt_file_with_metadata(file_path)
                    break
                except shutil.Error as e:
                    print(f"Error downloading file: {e}")
        else:
            print(f"{filename} could not be found.")

  # Securely delete the key file by overwriting with zeros
    def secure_delete(self, file_path):
        with open(file_path, "r+b") as f:
            file_size = os.path.getsize(file_path)
            # Overwrite the file with zeros
            for _ in range(file_size):
                f.write(chr(48).encode())
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"File could not be deleted: {e}")
    # Securely delete the key file by overwriting with random data
    def secure_delete_random(self, file_path):
        with open(file_path, "r+b") as f:
            file_size = os.path.getsize(file_path)
            # Overwrite the file with random data
            for _ in range(file_size):
                f.write(bytes([random.randint(0, 255)]))
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"File could not be deleted: {e}")

    # Remove folder   
    def delete_folder(self,folder_path):
        try:
            shutil.rmtree(folder_path)
        except Exception as e:
            print(f"The folder could not be deleted: {e}")



client = Client()

print("Command options: 'u' to upload a file, 'd' to download a file, 'l' to list all files, 'secure_delete' to overwrite the key or 'h' to see additional info or 'exit' to close the program.")

while True:
    user_input = input()

    if user_input == 'u':
        client.upload_file()

    elif user_input == 'd':
        client.download_file()

    elif user_input == 'l':
        client.list_files()
    
    elif user_input == 'secure_delete':
        # Get the name of the file to be securely deleted
        filename = input("Enter the name of the key file to securely delete (include file extension): ")
        file_name_without_extension = os.path.splitext(filename)[0]
        folder_path = os.path.join(client.folder_path, file_name_without_extension)
        file_path = os.path.join(folder_path, filename)

        if os.path.exists(file_path):
            secure_delete_option = input("Enter '0' to securely delete with zeros or '1' to securely delete with random data: ")
            file_path_key = file_path + ".key"
            if secure_delete_option == '0':
                client.secure_delete(file_path)
                client.secure_delete(file_path_key)
                client.delete_folder(folder_path)
                print(f"{filename} has been securely deleted with zeros.")
            elif secure_delete_option == '1':
                client.secure_delete_random(file_path)
                client.secure_delete_random(file_path_key)
                client.delete_folder(folder_path)
                print(f"{filename} has been securely deleted with random data.")
            else:
                print("Invalid option. Please try again.")
        else:
            print(f"{filename} could not be found.")

    elif user_input == 'exit':
        print("Exiting program...")
        sys.exit()
    
    elif user_input == 'h':
        print("u : All uploaded files are created in the 'Uploads' folder located on the desktop.")
        print("      Within this folder, a subfolder will be created where the uploaded file and its metadata will be stored.")
        print("      To upload a file you only have to enter the file name with its extention and the corresponding access route.")
        print("d : All downloaded files are by default saved in your local 'Downloads' folder.")
        print("      To download a file you only have to enter the file name with its extention.")
        print("l : This will display a list of all uploaded files.")
        print("secure_delete: To overwrite the files with zeros or random data and delete.")
        print("exit : This will close the program.")
        print("\nEnter a new command: 'u', 'd', 'l', or 'exit'")

    else:
        print("Invalid command")

    if user_input != 'h':
        print("\nEnter a new command: 'u', 'd', 'l', 'h', 'secure_delete' or 'exit'")
