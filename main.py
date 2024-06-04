import os
import subprocess

def find_and_run_userbots():
    # Dapatkan direktori kerja saat ini
    current_directory = os.getcwd()
    
    # Iterasi melalui semua folder dan file di dalam direktori kerja saat ini
    for root, dirs, files in os.walk(current_directory):
        for file in files:
            if file == "userbot.py":
                # Path lengkap ke file userbot.py
                full_path = os.path.join(root, file)
                print(f"Menjalankan {full_path}")
                # Menjalankan file userbot.py
                subprocess.run(["python", full_path], check=True)

if __name__ == "__main__":
    find_and_run_userbots()
