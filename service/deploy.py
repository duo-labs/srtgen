#!/usr/bin python3

CHALICE_BIN =  "chalice"
AWS_PROFILE = "srtgen_deploy"
CHALICE_APP_DIR = "./srtGenService"

##Quick example deploy script

import sys
import subprocess

print("[+] Deploying srtGenService to AWS....")

try:
    proc = subprocess.run([CHALICE_BIN, "deploy", "--profile", AWS_PROFILE], cwd=CHALICE_APP_DIR, capture_output=True)
except Exception as err:
    print("[-] Problem deploying app: %s"%(err))
    sys.exit(-1)


print("[+] App deployed") 
api_url = proc.stdout.split()[-1].decode("utf-8")
print("[+] API URL is: %s"%(api_url))

config_data="""
[srtGen]
API_URL = %s
FFMPEG_BIN_PATH = ffmpeg
"""%(api_url)

with open("config.ini", "w") as fo:
    fo.writelines(config_data)

print("[+] Config file written to 'config.ini' ")
print("[+] Done")