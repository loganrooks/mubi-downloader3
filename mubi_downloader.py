import requests
import subprocess
import re
import base64
import time
import json
import os

mainurl = input("Enter config url: ")
response = requests.get(f'{mainurl}')
data=json.loads(response.text)
license_url = data["request"]["drm"]["cdms"]["widevine"]["license_url"]
mpd = data['request']['files']['dash']['cdns']['fastly']['avc_url']

license_1url = requests.get(f'{license_url}')
final_license = license_1url.text

filename = input("Enter file/folder name: ")
folder_path = f"ADDHERE" # make this a valid file path

kid = requests.get(mpd)
os.makedirs(folder_path, exist_ok=True)
try:
    text_track_url = data["request"]["text_tracks"][0]["url"]
    subs = requests.get(f'{text_track_url}')
    subs = subs.text
    os.makedirs(os.path.join(folder_path, filename), exist_ok=True)
    
    with open(os.path.join(folder_path, filename, f"{filename}.en.srt"), "w", encoding="utf-8") as file:
        file.write(subs)
except KeyError:
    print("No external subtitles, they might be hardcoded.")
result = re.search(r'cenc:default_KID="(\w{8}-(?:\w{4}-){3}\w{12})">', str(kid.text))
def get_pssh(keyId):
    array_of_bytes = bytearray(b'\x00\x00\x002pssh\x00\x00\x00\x00')
    array_of_bytes.extend(bytes.fromhex("edef8ba979d64acea3c827dcd51d21ed"))
    array_of_bytes.extend(b'\x00\x00\x00\x12\x12\x10')
    array_of_bytes.extend(bytes.fromhex(keyId.replace("-", "")))
    return base64.b64encode(bytes.fromhex(array_of_bytes.hex()))

# Extract the encryption key ID from the regular expression match and generate the PSSH box
kid = result.group(1).replace('-', '')
assert len(kid) == 32 and not isinstance(kid, bytes), "wrong KID length"
pssh = format(get_pssh(kid).decode('utf-8'))
json_data = {
    'license': f'{final_license}',
    'headers': '',
    'pssh': f'{pssh}',                                                
    'buildInfo': '',                                                 
    'proxy': '',                                                      
    'cache': False,                                                    
}

# Send a POST request with the headers and JSON data to the specified URL
response = requests.post('https://cdrm-project.com/wv', json=json_data)
result = re.search(r"[a-z0-9]{16,}:[a-z0-9]{16,}", str(response.text))
decryption_key = result.group()
print(decryption_key)
decryption_key = f'key_id={decryption_key}'
decryption_key = decryption_key.replace(":",":key=")
download = subprocess.run(fr'N_m3u8DL-RE "{mpd}"--auto-select --save-name "{filename}" --auto-select --save-dir {folder_path} --tmp-dir {folder_path}/temp', shell=True, capture_output=True, text=True)
print(download)
decrypt = subprocess.run(fr'shaka-packager in="{folder_path}/{filename}.m4a",stream=audio,output="{dest_dir}/decrypted-audio.m4a" --enable_raw_key_decryption --keys {decryption_key}') 
print(decrypt)
decrypt = subprocess.run(fr'shaka-packager in="{folder_path}/{filename}.mp4",stream=video,output="{dest_dir}/decrypted-video.mp4" --enable_raw_key_decryption --keys {decryption_key}')
print(decrypt)
subprocess.run(["rm", f"{folder_path}/{filename}.m4a"])
subprocess.run(["rm", f"{folder_path}/{filename}.mp4"])
