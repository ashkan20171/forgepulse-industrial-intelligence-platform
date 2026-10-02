import json, random, time
import paho.mqtt.client as mqtt
from .config import settings

def generate_sensor_data(step: int, offset=0):
    anomaly = step % 60 >= 52
    return {"timestamp":time.time(), "temperature":round(64+offset+random.uniform(-2.5,2.5)+(22 if anomaly else 0),2), "vibration":round(2.3+random.uniform(-.35,.35)+(5.2 if anomaly else 0),2), "pressure":round(5.5+random.uniform(-.2,.2),2), "rpm":round(1450+random.uniform(-25,25),0)}

def start_simulator():
    client=mqtt.Client(client_id="industrial-iot-simulator"); client.connect(settings.MQTT_BROKER, settings.MQTT_PORT, 60); client.loop_start()
    machines=[("motor_01",0),("pump_01",-5),("fan_01",3)]; step=0
    try:
        while True:
            for machine, offset in machines: client.publish(f"factory/sensor/{machine}/metrics", json.dumps(generate_sensor_data(step+offset, offset)))
            step+=1; time.sleep(2)
    except KeyboardInterrupt: pass
    finally: client.loop_stop(); client.disconnect()
if __name__ == "__main__": start_simulator()
