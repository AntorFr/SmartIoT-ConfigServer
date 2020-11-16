
import paho.mqtt.client as mqtt
import json

from smartiot_firmware import FirmwareWatcher 

config = {}

def load_config():
    global config
    with open('config.json', 'r') as f:
        config = json.load(f)
        if ("port" not in config["broker"]):
            config["broker"]["port"] = 1883

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    client.subscribe(config["domains"][0]+"/setup/ota/#")
    print("suscribed to: "+config["domains"][0]+"/setup/ota/#")
    post_firmwares()

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    #print(msg.topic+" "+str(msg.payload))
    return

def on_firmware_message(client, userdata, msg):
   topic=  msg.topic.split("/") 
   if (msg.retain == True and ( \
        topic[3] not in fw.firmwares or \
        topic[5] != fw.firmwares[topic[3]]["md5"])):
        print("firmware on "+msg.topic+" outdated, remove it")
        client.publish(msg.topic, payload="", qos=1, retain=True)


def post_firmwares():
    for fwname, firmware in fw.firmwares.items():
        post_firmware(firmware)
    
def post_firmware(firmware):
    for domain in config["domains"]:
        client.publish(domain+"/setup/ota/"+firmware["name"]+"/firmware/"+firmware["md5"], payload=fw.get_firmware_data(firmware["path"]), qos=1, retain=True)
        client.publish(domain+"/setup/ota/"+firmware["name"]+"/firmware", payload=json.dumps(firmware), qos=1, retain=True)
    firmware["published"]=True

def unpost_firmware(firmware):
    for domain in config["domains"]:
        client.publish(domain+"/setup/ota/"+firmware["name"]+"/firmware/"+firmware["md5"], payload="", qos=1, retain=True)
        client.publish(domain+"/setup/ota/"+firmware["name"]+"/firmware", payload="", qos=1, retain=True)
    firmware["published"]=False



if __name__ == "__main__":
    load_config()



    client = mqtt.Client(client_id="SmartIot_configServ")
    client.will_set(config["domains"][0]+"/setup/up/smartiot_configserv", payload='{"status":"Offline"}', qos=1, retain=True)
    if ("username" in config["broker"]):
        client.username_pw_set(config["broker"]["username"], password=config["broker"]["password"])
    client.on_connect = on_connect
    client.on_message = on_message
    for domain in config["domains"]:
        client.message_callback_add(domain+"/setup/ota/+/firmware/+", on_firmware_message)

    client.connect(config["broker"]["host"], config["broker"]["port"], 60)

    fw = FirmwareWatcher("./firmwares")
    fw.add = post_firmware
    fw.remove = unpost_firmware
    fw.read_firmware_folder()
    print(fw.firmwares)


    try:
        client.loop_forever()
    except (SystemExit, KeyboardInterrupt):
        fw.observer.stop()
        client.disconnect()
    fw.observer.join()