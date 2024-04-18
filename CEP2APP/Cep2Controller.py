from Cep2Model import Cep2Model
from Cep2WebClient import Cep2WebClient, Cep2WebDeviceEvent
from Cep2Zigbee2mqttClient import (Cep2Zigbee2mqttClient,
                                   Cep2Zigbee2mqttMessage, Cep2Zigbee2mqttMessageType)
import time
from datetime import datetime
from threading import Thread

class Cep2Controller:
    HTTP_HOST = "http://localhost:8000"
    MQTT_BROKER_HOST = "localhost"
    MQTT_BROKER_PORT = 1883
    activationTime = datetime(2024, 4, 11, 11, 31)
    currentRoom = "Stue"

    """ The controller is responsible for managing events received from zigbee2mqtt and handle them.
    By handle them it can be process, store and communicate with other parts of the system. In this
    case, the class listens for zigbee2mqtt events, processes them (turn on another Zigbee device)
    and send an event to a remote HTTP server.
    """

    def __init__(self, devices_model: Cep2Model) -> None:
        """ Class initializer. The actuator and monitor devices are loaded (filtered) only when the
        class is instantiated. If the database changes, this is not reflected.

        Args:
            devices_model (Cep2Model): the model that represents the data of this application
        """
        self.__devices_model = devices_model
        self.__z2m_client = Cep2Zigbee2mqttClient(host=self.MQTT_BROKER_HOST,
                                                  port=self.MQTT_BROKER_PORT,
                                                  on_message_clbk=self.__zigbee2mqtt_event_received)

    def timeLoop(self):
        while(True):
            nowTime = datetime.now()
            if(nowTime > self.activationTime and self.currentRoom == "livingRoom"): 
                self.__z2m_client.change_state("glowyBoi", "ON")
            # Only proceed if we're not already in the middle of a blinking sequence
            time.sleep(1) # Delay 1 second

    def start(self) -> None:
        """ Start listening for zigbee2mqtt events.
        """
        self.__z2m_client.connect()
        timeThread = Thread(target=self.timeLoop)
        timeThread.start()
        print("Thread started")
        print(f"Zigbee2Mqtt is {self.__z2m_client.check_health()}")

    def stop(self) -> None:
        """ Stop listening for zigbee2mqtt events.
        """
        self.__z2m_client.disconnect()

    def __zigbee2mqtt_event_received(self, message: Cep2Zigbee2mqttMessage) -> None:
        """ Process an event received from zigbee2mqtt. This function given as callback to
        Cep2Zigbee2mqttClient, which is then called when a message from zigbee2mqtt is received.

        Args:
            message (Cep2Zigbee2mqttMessage): an object with the message received from zigbee2mqtt
        """
        # If message is None (it wasn't parsed), then don't do anything.
        if not message:
            return

        print(
            f"zigbee2mqtt event received on topic {message.topic}: {message.data}")

        # If the message is not a device event, then don't do anything.
        if message.type_ != Cep2Zigbee2mqttMessageType.DEVICE_EVENT:
            return

        # Parse the topic to retreive the device ID. If the topic only has one level, don't do
        # anything.
        tokens = message.topic.split("/")
        if len(tokens) <= 1:
            return

        # Retrieve the device ID from the topic.
        device_id = tokens[1]

        # If the device ID is known, then process the device event and send a message to the remote
        # web server.
        device = self.__devices_model.find(device_id)

        if device:
            try:
                occupancy = message.event["occupancy"]
            except KeyError:
                pass
            else:
                # Based on the value of occupancy, change the state of the actuators to ON
                # (occupancy is true, i.e. a person is present in the room) or OFF.
                self.currentRoom = device_id if occupancy else self.currentRoom
                print(f"Current room is {self.currentRoom}")
                """
                # Change the state on all actuators, i.e. LEDs and power plugs.
                for a in self.__devices_model.actuators_list:
                    self.__z2m_client.change_state(a.id_, "ON")

                # Register event in the remote web server.
                web_event = Cep2WebDeviceEvent(device_id=device.id_,
                                               device_type=device.type_,
                                               measurement=occupancy)

                client = Cep2WebClient(self.HTTP_HOST)
                try:
                    client.send_event(web_event.to_json())
                except ConnectionError as ex:
                    print(f"{ex}")
                """