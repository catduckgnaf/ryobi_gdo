import requests
import logging
import websocket
import json

class RyobiApiClient:
    """Class for interacting with the Ryobi Garage Door Opener API."""

    HOST_URI = "tti.tiwiconnect.com"
    LOGIN_ENDPOINT = "api/login"
    DEVICE_GET_ENDPOINT = "api/devices"
    DEVICE_SET_ENDPOINT = "api/wsrpc"

    STATE_DOOR_OPEN = 'open'
    STATE_DOOR_CLOSED = 'closed'
    STATE_DOOR_OPENING = 'opening'
    STATE_LIGHT_ON = 'on'
    STATE_LIGHT_OFF = 'off'

    REQUEST_TIMEOUT = 3

    DOOR_STATE = {
        '0': STATE_DOOR_CLOSED,
        '1': STATE_DOOR_OPEN,
        '3': STATE_DOOR_OPENING,
    }

    LIGHT_STATE = {
        'False': STATE_LIGHT_OFF,
        'True': STATE_LIGHT_ON,
    }

    logger = logging.getLogger(__name__)

    def __init__(self, username, password, device_id):
        """Initialize the API object."""
        self.username = username
        self.password = password
        self.device_id = device_id
        self.door_state = None
        self.light_state = None
        self.battery_level = None
        self.api_key = None
        from websocket import create_connection
        self._connection = create_connection

    def get_api_key(self):
        """Getting api_key from Ryobi."""
        auth_ok = False
        for attempt in range(5):
            try:
                resp = requests.post('https://{}/{}'.format(self.HOST_URI, self.LOGIN_ENDPOINT), timeout=self.REQUEST_TIMEOUT, data={
                    'username': self.username,
                    'password': self.password
                    })
            except requests.exceptions.RequestException:
                print("Exception while requesting Ryobi to get API Key")
            else:
                break
        if(resp.status_code == 200):
            try:
                resp_meta = resp.json()['result']['metaData']
                self.api_key = resp_meta['wskAuthAttempts'][0]['apiKey']
                auth_ok = True
            except KeyError:
                print("Exception while parsing Ryobi answer to get API key")
                return False
        return auth_ok

    def check_device_id(self):
        """Checking device_id from Ryobi."""
        device_found = False
        answer = False
        for attempt in range(5):
            try:
                resp = requests.get("https://{}/{}".format(self.HOST_URI, self.DEVICE_GET_ENDPOINT), timeout=self.REQUEST_TIMEOUT, data={
                    'username': self.username,
                    'password': self.password
                })
            except requests.exceptions.RequestException:
                print("Exception while requesting Ryobi to check device ID")
            else:
                answer = True
                break
        if(answer == True and resp.status_code == 200):
            try:
                result = resp.json()['result']
            except KeyError:
                return device_found
        if len(result) == 0:
            print("empty result")
        else:
            for data in result:
                if data['varName'] == self.device_id:
                    device_found = True
        return device_found

    def update(self):
        """Update door status from Ryobi."""
        update_ok = False
        answer = False
        for attempt in range(5):
            try:
                resp = requests.get("https://{}/{}/{}".format(self.HOST_URI, self.DEVICE_GET_ENDPOINT, self.device_id), timeout=self.REQUEST_TIMEOUT, data={
                    'username': self.username,
                    'password': self.password
                })
            except requests.exceptions.RequestException:
                print("Exception while requesting Ryobi to update device")
            else:
                answer = True
                break
        if(answer == True and resp.status_code == 200):
            try:
                gdo_status = resp.json()
                dtm = gdo_status['result'][0]['deviceTypeMap']
                door_state = dtm['garageDoor_7']['at']['doorState']['value']
                self.door_state = self.DOOR_STATE[str(door_state)]
                light_state = dtm['garageLight_7']['at']['lightState']['value']
                self.light_state = self.LIGHT_STATE[str(light_state)]
                self.battery_level = dtm['backupCharger_8']['at']['chargeLevel']['value']
                update_ok = True
            except KeyError:
                print("Exception while parsing answer to update device")
                return update_ok
        return update_ok

    def get_door_status(self):
        """Get current door status."""
        return self.door_state

    def get_battery_level(self):
        """Get current battery level."""
        return self.battery_level

    def get_light_status(self):
        """Get current light status."""
        return self.light_state

    def get_device_id(self):
        """Get device_id."""
        return self.device_id

    def close_device(self):
        """Close Device."""
        return self.send_message("doorCommand", 0)

    def open_device(self):
        """Open Device."""
        return self.send_message("doorCommand", 1)

    def send_message(self, command, value):
        """Generic send message."""
        from websocket import _exceptions
        ws_auth = False
        for attempt in range(5):
            try:
                websocket = self._connection('wss://{host_uri}/{device_set_endpoint}'.format(
                    host_uri=self.HOST_URI,
                    device_set_endpoint=self.DEVICE_SET_ENDPOINT), timeout=self.REQUEST_TIMEOUT)
                auth_mssg = json.dumps(
                    {'jsonrpc': '2.0',
                        'id': 3,
                        'method': 'srvWebSocketAuth',
                        'params': {
                            'varName': self.username,
                            'apiKey': self.api_key}})
                websocket.send(auth_mssg)
                result = websocket.recv()
            except Exception as ex:
                print("Exception during websocket authentification")
                websocket.close()
            else:
                ws_auth = True
                break
        if (ws_auth == True):
            for attempt in range(5):
                try:
                    pay_load = json.dumps({'jsonrpc': '2.0',
                                           'method': 'gdoModuleCommand',
                                           'params':
                                           {'msgType': 16,
                                            'moduleType': 5,
                                            'portId': 7,
                                            'moduleMsg': {command: value},
                                            'topic': self.device_id}})
                    websocket.send(pay_load)
                    pay_load = ""
                    result = websocket.recv()
                except Exception as ex:
                    print("Exception during sending message")
                    websocket.close()
                else:
                    break
        websocket.close()
