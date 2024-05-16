from hmac import new
from itertools import count
from Cep2Model import Cep2Model
from Cep2WebClient import Cep2WebClient, Cep2WebDeviceEvent
from Cep2Zigbee2mqttClient import (Cep2Zigbee2mqttClient,
                                   Cep2Zigbee2mqttMessage, Cep2Zigbee2mqttMessageType)
import time
from datetime import datetime, timedelta
from threading import Thread

class Cep2Controller:
    HTTP_HOST = "http://172.20.10.6/receive_data.php"  # Replace with your server's IP
    HTTP_HOST_RETRIEVE = "http://172.20.10.6/retrieve_variables.php"
    MQTT_BROKER_HOST = "localhost"
    MQTT_BROKER_PORT = 1883
    medicationTime = datetime(2024, 5, 16, 16, 18)
    timeWindowBefore = 1
    timeWindowAfter = 1
    dailyUpdateTime = datetime(2024, 5, 16, 14, 13)
    currentRoom = "Stue"
    runningThread = True
    medicationTaken = False
    HeucodNum = 0
    EventDescription = ""
    sensorToActuator = {
        "bedRoom": "bedroomLight",
        "livingRoom": "livingroomLight",
    }

    def __init__(self, devices_model: Cep2Model) -> None:
        self.__devices_model = devices_model
        self.__z2m_client = Cep2Zigbee2mqttClient(host=self.MQTT_BROKER_HOST,
                                                  port=self.MQTT_BROKER_PORT,
                                                  on_message_clbk=self.__zigbee2mqtt_event_received)

    def timeLoop(self):
        while self.runningThread:
            nowTime = datetime.now()
            if nowTime > self.dailyUpdateTime:
                client = Cep2WebClient(self.HTTP_HOST_RETRIEVE)
                var1, self.timeWindowBefore, self.timeWindowAfter = client.retrieve_variables()
                self.medicationTime = datetime(2024, 5, 16, var1[0], var1[1])
                print(self.timeWindowBefore)
                self.medicationTaken = False
                self.dailyUpdateTime = self.dailyUpdateTime + timedelta(days=1)

            if nowTime > self.medicationTime + timedelta(minutes=self.timeWindowAfter):
                if self.currentRoom in self.sensorToActuator:
                    self.__z2m_client.change_state(self.sensorToActuator[self.currentRoom], "ON", 0.7, 0.29)
                else:
                    print(f"Unknown room: {self.currentRoom}")
                self.__z2m_client.change_state("kitchenLight", "ON", 0.7, 0.29)

            elif nowTime > self.medicationTime:
                if self.currentRoom in self.sensorToActuator:
                    self.__z2m_client.change_state(self.sensorToActuator[self.currentRoom], "ON", 0.45, 0.5)
                else:
                    print(f"Unknown room: {self.currentRoom}")
                self.__z2m_client.change_state("kitchenLight", "ON", 0.45, 0.5)

            elif nowTime > self.medicationTime - timedelta(minutes=self.timeWindowBefore):
                if self.currentRoom in self.sensorToActuator:
                    self.__z2m_client.change_state(self.sensorToActuator[self.currentRoom], "ON", 0.15, 0.75)
                else:
                    print(f"Unknown room: {self.currentRoom}")
                self.__z2m_client.change_state("kitchenLight", "ON", 0.15, 0.75)

            time.sleep(5) # Delay 5 seconds

    def start(self) -> None:
        self.__z2m_client.connect()
        timeThread = Thread(target=self.timeLoop)
        timeThread.start()
        print("Thread started")
        print(f"Zigbee2Mqtt is {self.__z2m_client.check_health()}")

    def blink(self, light_sensor_id) -> None:
        counter = 0
        while counter <= 1:
            self.__z2m_client.change_state(light_sensor_id, "ON", 0.7, 0.28)
            time.sleep(1)
            self.__z2m_client.change_state(light_sensor_id, "OFF", 0.7, 0.28)
            time.sleep(1)
            counter += 1
        return

    def stop(self) -> None:
        self.__z2m_client.disconnect()

    def __zigbee2mqtt_event_received(self, message: Cep2Zigbee2mqttMessage) -> None:
        occupancy = False
        if not message:
            return

        print(
            f"zigbee2mqtt event received on topic {message.topic}: {message.data}")

        if message.type_ != Cep2Zigbee2mqttMessageType.DEVICE_EVENT:
            return

        tokens = message.topic.split("/")
        if len(tokens) <= 1:
            return

        device_id = tokens[1]

        device = self.__devices_model.find(device_id)

        new_update = False
        if device_id == "pillboxSensor":
            vibration = message.event["vibration"]
            nowTime = datetime.now()
            if vibration and nowTime > self.medicationTime - timedelta(minutes=self.timeWindowBefore) and self.medicationTaken == False:
                self.__z2m_client.change_state("kitchenLight", "OFF", 0, 0)
                self.__z2m_client.change_state(self.sensorToActuator[self.currentRoom], "OFF", 0, 0)
                self.medicationTime = self.medicationTime + timedelta(days=1)
                self.runningThread = True
                self.medicationTaken = True
                self.HeucodNum = 82295
                self.EventDescription = "Medication taken"
                print("Medication has been taken")
                new_update = True

            elif vibration:
                self.HeucodNum = 81493
                self.EventDescription = "Pillbox moved outside window"
                print("ERROR")
                new_update = True
                self.blink("kitchenLight")
                

        if device_id == "bedRoom" or device_id == "livingRoom":
            occupancy = message.event["occupancy"]
        
        
        if occupancy:
            nowTime = datetime.now()
            if device_id != self.currentRoom and not self.medicationTaken and nowTime > self.medicationTime - timedelta(minutes=self.timeWindowBefore):
                self.__z2m_client.change_state(self.sensorToActuator[self.currentRoom], "OFF", 0, 0)
                self.__z2m_client.change_state(self.sensorToActuator[device_id], "ON", 0.15, 0.75)
                self.currentRoom = device_id
                new_update = True
                print(f"Current room is {self.currentRoom}")
            else:
                self.currentRoom = device_id
                new_update = True
                print(f"Current room is {self.currentRoom}")
            self.HeucodNum = 82099
            self.EventDescription = occupancy
            new_update = True




        if new_update:
            print("sending event")
            web_event = Cep2WebDeviceEvent(device_id=device.id_,
                                            device_type=device.type_,
                                            measurement=self.EventDescription,
                                            heucod_event=self.HeucodNum)
            client = Cep2WebClient(self.HTTP_HOST)
            try:
                status_code = client.send_event(web_event.to_heucod())
                print(f"Status code: {status_code}")
            except ConnectionError as ex:
                print(f"{ex}")