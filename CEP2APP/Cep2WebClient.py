import json
from dataclasses import dataclass
from typing import Any
from Cep2Heucod import HeucodEvent
import requests
from datetime import datetime


@dataclass
class Cep2WebDeviceEvent:
    """ Represents a device event that is sent to the remote web service.
    """
    device_id: str
    device_type: str
    measurement: Any
    heucod_event: int

    def to_heucod(self) -> str:

        event_heucod = HeucodEvent()
        event_heucod.id = self.device_id
        event_heucod.event_type = str(self.heucod_event)
        event_heucod.event_type_enum = self.heucod_event
        event_heucod.description = self.measurement
        event_heucod.timestamp = datetime.now().isoformat()
        event_heucod.device_model = self.device_type


        return event_heucod.to_json()


class Cep2WebClient:
    """ Represents a local web client that sends events to a remote web service.
    """

    def __init__(self, host: str) -> None:
        """ Default initializer.

        Args:
            host (str): an URL with the address of the remote web service
        """
        self.__host = host

    def send_event(self, event: str) -> int:
        """ Sends a new event to the web service.

        Args:
            event (str): a string with the event to be sent.

        Raises:
            ConnectionError: if the connection to the web service fails

        Returns:
            int: the status code of the request
        """
        try:
            # A new event is sent as an HTTP POST request.
            response = requests.post(self.__host, data=event)

            return response.status_code
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Error connecting to {self.__host}")
    
    def retrieve_variables(self) -> tuple:
        """ Retrieves three variables from the PHP server.

        Returns:
            tuple: a tuple containing three variables retrieved from the server
        """
        try:
            # Send a GET request to retrieve the variables from the server
            response = requests.get(self.__host)

            # Parse the response and extract the variables
            data = response.json()
            var1 = data.get('variable1')
            var2 = data.get('variable2')
            var3 = data.get('variable3')

            return var1, var2, var3
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Error connecting to {self.__host}")
        except Exception as e:
            # Handle any other exceptions gracefully
            raise RuntimeError(f"Error retrieving variables: {e}")