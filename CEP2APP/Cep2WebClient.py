import json
from dataclasses import dataclass
from typing import Any
from Cep2Heucod import HeucodEvent, HeucodEventJsonEncoder
import requests
from datetime import datetime

@dataclass
class Cep2WebDeviceEvent:
    device_id: str
    device_type: str
    measurement: Any
    heucod_event: int

    # function for converting to Heucod format using the HeucodEvent class
    def to_heucod(self) -> str:
        event_heucod = HeucodEvent()
        event_heucod.id = self.device_id
        event_heucod.event_type_enum = self.heucod_event
        event_heucod.description = self.measurement
        event_heucod.timestamp = datetime.now().isoformat()
        event_heucod.device_model = self.device_type

        return event_heucod.to_json()

class Cep2WebClient:
    def __init__(self, host: str) -> None:
        self.__host = host

    def send_event(self, event: str) -> int:
        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(self.__host, data=event, headers=headers)

            return response.status_code
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Error connecting to {self.__host}")
    
    #this function retrieves the potentially new medication time from the server
    def retrieve_variables(self) -> tuple:
        try:
            response = requests.get(self.__host)
            data = response.json()
            var1 = data.get('variable1', [0, 0])  # Default to [0, 0] if not found
            var2 = data.get('variable2', 0)  # Default to 0 if not found
            var3 = data.get('variable3', 0)  # Default to 0 if not found

            return var1, var2, var3
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Error connecting to {self.__host}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving variables: {e}")