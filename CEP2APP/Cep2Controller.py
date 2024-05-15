from hmac import new
from itertools import count
from arrow import now
from Cep2Model import Cep2Model
from Cep2WebClient import Cep2WebClient, Cep2WebDeviceEvent
from Cep2Zigbee2mqttClient import (Cep2Zigbee2mqttClient,
                                   Cep2Zigbee2mqttMessage, Cep2Zigbee2mqttMessageType)
import time
from datetime import datetime, timedelta
from threading import Thread

class Cep2Controller:
    HTTP_HOST = "172.20.10.6"
    MQTT_BROKER_HOST = "localhost"
    MQTT_BROKER_PORT = 1883
    medicationTime = datetime(2024, 5, 16, 9, 5)
    timeWindowBefore = 15
    timeWindowAfter = 15
    dailyUpdateTime = datetime(2024, 5, 16, 23, 59)
    currentRoom = "Stue"
    runningThread = True
    medicationTaken = False
    sensorToActuator = {"bedroom": "glowyBoi", "livingroom": "livingroomLight"}


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
        while(self.runningThread):
            nowTime = datetime.now()
            if(nowTime > self.dailyUpdateTime):
                client = Cep2WebClient(self.HTTP_HOST)
                var1, self.timeWindowBefore, self.timeWindowAfter = client.retrieve_variables()
                self.medicationTime = datetime(2024, 5, 16, var1[0], var1[1])
                self.medicationTaken = False
                self.dailyUpdateTime = self.dailyUpdateTime + timedelta(days=1)

            if(nowTime > self.medicationTime + timedelta(minutes=self.timeWindowAfter)):
                self.__z2m_client.change_state(self.sensorToActuator[self.currentRoom], "ON", 0, 0)
                self.__z2m_client.change_state("kitchenLight", "ON", 0.15, 0.75)

            elif(nowTime > self.medicationTime): 
                self.__z2m_client.change_state(self.sensorToActuator[self.currentRoom], "ON", 0.15, 0.75)
                self.__z2m_client.change_state("kitchenLight", "ON", 0.15, 0.75)

            elif(nowTime > self.medicationTime - timedelta(minutes=self.timeWindowBefore)):
                self.__z2m_client.change_state(self.sensorToActuator[self.currentRoom], "ON", 0.15, 0.75)
                self.__z2m_client.change_state("kitchenLight", "ON", 0.15, 0.75)

            time.sleep(5) # Delay 5 seconds

    def start(self) -> None:
        """ Start listening for zigbee2mqtt events.
        """
        self.__z2m_client.connect()
        timeThread = Thread(target=self.timeLoop)
        timeThread.start()
        print("Thread started")
        print(f"Zigbee2Mqtt is {self.__z2m_client.check_health()}")

    def blink(self, light_sensor_id) -> None:
        counter = 0
        while(counter < 5):
            self.__z2m_client.change_state(light_sensor_id, "ON", 0.7, 0.28)
            time.sleep(1)
            self.__z2m_client.change_state(light_sensor_id, "OFF", 0.7, 0.28)
            time.sleep(1)
            counter += 1
        return

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

        new_update = False
        if(device_id == "vibratingBoi"):
            vibration = message.event["vibration"]
            nowTime = datetime.now()
            if vibration and nowTime > self.medicationTime - self.timeWindowBefore:
                self.__z2m_client.change_state(self.sensorToActuator[self.currentRoom], "OFF", 0, 0)
                self.__z2m_client.change_state("kitchenLight", "OFF", 0, 0)
                self.medicationTime = self.medicationTime + timedelta(days=1)
                self.runningThread = True
                self.medicationTaken = True
                web_event = Cep2WebDeviceEvent(device_id=device.id_,
                                               device_type=device.type_,
                                               measurement="Medication taken",
                                               heucod_event=82295)
                new_update = True

            elif vibration and (nowTime < (self.medicationTime - self.timeWindowBefore) or self.medicationTaken == True):
                self.blink("kitchenLight")
                web_event = Cep2WebDeviceEvent(device_id=device.id_,
                                               device_type=device.type_,
                                               measurement="Pillbox moved outside window",
                                               heucod_event=81493)
                new_update = True
                
        if device:
            try:
                occupancy = message.event["occupancy"]
            except KeyError:
                pass
            else:
                # Based on the value of occupancy, change the state of the actuators to ON
                # (occupancy is true, i.e. a person is present in the room) or OFF.
                nowTime = datetime.now()
                if(device_id != self.currentRoom and self.medicationTaken == False and occupancy and nowTime > self.medicationTime - timedelta(minutes=self.timeWindowBefore)):
                    self.__z2m_client.change_state(self.sensorToActuator[self.currentRoom], "OFF", 0, 0)
                    self.__z2m_client.change_state(self.sensorToActuator[device_id], "ON", 0.15, 0.75)
                    self.currentRoom = device_id
                    new_update = True
                    print(f"Current room is {self.currentRoom}")
                elif(device_id != self.currentRoom and occupancy):
                    self.currentRoom = device_id
                    new_update = True
                    print(f"Current room is {self.currentRoom}")
                # Register event in the remote web server.
                web_event = Cep2WebDeviceEvent(device_id=device.id_,
                                               device_type=device.type_,
                                               measurement=occupancy,
                                               heucod_event=82099)
        if(new_update):
            client = Cep2WebClient(self.HTTP_HOST)
            new_update = False
            try:
                client.send_event(web_event.to_heucod())
            except ConnectionError as ex:
                print(f"{ex}")
        