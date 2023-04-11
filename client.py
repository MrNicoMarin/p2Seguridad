import os
import shutil
from cryptography.fernet import Fernet


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
                    print(f"\n{filename} has been uploaded to the subfolder '{os.path.splitext(filename)[0]}' in the 'Uploads' folder.")
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


    def download_files (self):
        filename = input("Enter the name of the file to download (include file extension): ")

        for root, _, files in os.walk(self.folder_path):
            if filename in files:
                file_path = os.path.join(root, filename)
                #Decrypt file before downloading
                self.decrypt(file_path)
                download_path = os.path.join(os.path.expanduser("~"), "Downloads", filename)
                try:
                    shutil.copy(file_path, download_path)
                    print(f"\n{filename} has been downloaded to '{download_path}'.")
                except shutil.Error as e:
                    print(f"Error downloading file: {e}")
                # Encrypt the file before uploading
                self.encrypt(file_path)
                break
        else:
            print(f"{filename} could not be found.")



client = Client()

print("Command options: 'u' to upload a file, 'd' to download a file, 'l' to list all files, 'h' to see additional info\n")

while True:
    user_input = input()

    if user_input == 'u':
        client.upload_file()

    elif user_input == 'd':
        client.download_files()

    elif user_input == 'l':
        client.list_files()

    elif user_input == 'h':
        print("'u' : All uploaded files are created in the 'Uploads' folder located on the desktop." 
                   " Within this folder, a subfolder will be created where the uploaded file and its metadata will be stored."
                   " To upload a file you only have to enter the file name with its extention (e. g. 'upload_file.pdf') and the corresponding access route (e.g. C:\Users\user\Desktop\upload_file.pdf).\n"
              "'d' : All downloaded files are by default saved in your local 'Downloads' folder."
                   " To download a file you only have to enter the file name with its extention (e. g. 'download_file.pdf')\n"
              "'l' : This will display a list of all uploaded files.\n")
        
    else:
        print("Invalid command")

    if user_input != 'h':
        print("\nEnter 'h' for help, or enter a command ('u', 'd', 'l')")
