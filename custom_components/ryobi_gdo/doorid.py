## for simplified testing, will remove

import requests

username = ""
password = ""

uandp = {"username": username, "password": password}

# Perform a POST request to login
r = requests.post("https://tti.tiwiconnect.com/api/login", data=uandp)

# Print the login response content
print("Login Response:", r.text)

# Perform a GET request to retrieve devices
s = requests.get("https://tti.tiwiconnect.com/api/devices", params=uandp)

# Print the device retrieval response content
print("Device Retrieval Response:", s.text)

# Check if the request was successful
if r.status_code == 200 and s.status_code == 200:
    # Iterate through the devices and print relevant information
    for result in s.json()["result"]:
        if "gdoMasterUnit" in result["deviceTypeIds"]:
            print(result["metaData"]["name"], "- Device ID:", result["varName"])
else:
    print("Login or device retrieval failed. Check the responses and try again.")
