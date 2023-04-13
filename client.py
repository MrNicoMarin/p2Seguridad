import os
import shutil
import sys
from cryptography.fernet import Fernet
import datetime
import json


class Client:

    def __init__(self):

        # set the folder path for local file uploads
        self.desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        self.folder_path = os.path.join(self.desktop_path, "Uploads")

        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)

        # Generate a Fernet key
        self.key = Fernet.generate_key()


     # Encrypt the file using the Fernet key
    def encrypt(self, file_path):
        
        with open(file_path, "rb") as f:
            data = f.read()

        fernet = Fernet(self.key)
        encrypted = fernet.encrypt(data)

        # Write the encrypted data to the file
        with open(file_path, "wb") as f:
            f.write(encrypted)


    # Decrypt the file using the Fernet key
    def decrypt(self, file_path):
        with open(file_path, "rb") as f:
            data = f.read()

        fernet = Fernet(self.key)
        decrypted = fernet.decrypt(data)

        # Write the decrypted data to the file
        with open(file_path, "wb") as f:
            f.write(decrypted)


    def upload_file(self):
        filename = input("Enter the name of the file to upload (include file extension): ")

        # create a subfolder with the same name as the file to upload
        subfolder_path = os.path.join(self.folder_path, os.path.splitext(filename)[0])
        if not os.path.exists(subfolder_path):
            os.makedirs(subfolder_path)

        # construct the full path of the file to upload
        file_path = os.path.join(subfolder_path, filename)

        if os.path.exists(file_path):
            overwrite = input(f"'{filename}' already exists in the 'Uploads' folder. Do you want to overwrite it? (y/n): ")
            if overwrite.lower() == 'n':
                return print(f"'{filename}' has not been overwritten.")
        
        while True: 
            upload_path = input("Enter the path of the file to upload: ")
            if os.path.exists(upload_path):
                try:
                    # copy the file to the subfolder
                    shutil.copy(upload_path, file_path)
                    # Encrypt the file before uploading
                    self.encrypt(file_path)
                    print(f"\n{filename} has been successfully uploaded.")
                    # Save metadata in a file
                    metadata = {
                        "filename": filename,
                        "size": os.path.getsize(file_path),
                        "upload_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    with open(os.path.join(subfolder_path, "metadata"), "w") as f:
                        json.dump(metadata, f)
                    print("Key : ", self.key.decode())
                    break
                except shutil.Error as e:
                    print(f"Error uploading file: {e}")
            else:
                print("Invalid file path. Please try again.")


    def list_files(self):
        print("List of all uploaded files:")
        for root, _, files in os.walk(self.folder_path):
            for filename in files:
                print(f"- {filename}")


    def download_file(self):
        filename = input("Enter the name of the file to download (include file extension): ")

        for root, _, files in os.walk(self.folder_path):
            if filename in files:
                file_path = os.path.join(root, filename)
                #Decrypt file before downloading
                self.decrypt(file_path)
                download_path = os.path.join(os.path.expanduser("~"), "Downloads", filename)
                try:
                    shutil.copy(file_path, download_path)
                    print(f"\n{filename} has been successfully downloaded.")
                except shutil.Error as e:
                    print(f"Error downloading file: {e}")
                # Encrypt the file before uploading
                self.encrypt(file_path)
                break
        else:
            print(f"{filename} could not be found.")


client = Client()

print("Command options: 'u' to upload a file, 'd' to download a file, 'l' to list all files or 'h' to see additional info or 'exit' to close the program.")

while True:
    user_input = input()

    if user_input == 'u':
        client.upload_file()

    elif user_input == 'd':
        client.download_file()

    elif user_input == 'l':
        client.list_files()
    
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
        print("exit : This will close the program.")
        print("\nEnter a new command: 'u', 'd', 'l', or 'exit'")

    else:
        print("Invalid command")

    if user_input != 'h':
        print("\nEnter a new command: 'u', 'd', 'l', 'h' or 'exit'")
