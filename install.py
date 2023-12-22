import os
import sys
import subprocess



def shell(command):
    result = subprocess.run(command, shell=True)
    if result.returncode != 0:
        print(f"Error running {' '.join(command)}")
        sys.exit(1)



py_command = input("What is your command to invoke python?")

shell(f"{py_command} -m venv venv")

if os.name == "nt":
    shell(f".\\venv\\Scripts\\activate")
else:
    shell(f"source ./venv/bin/activate")

shell("pip install -r requirements.txt")

shell(f"{py_command} -m spacy download en_core_web_sm")

print("Installation complete.")