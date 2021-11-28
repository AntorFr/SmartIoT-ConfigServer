from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import os, json, time
from collections.abc import Mapping

def incarnate_settings(data,settings):
    new = {}
    for k, v in data.items():
        if isinstance(v, dict):
            v = incarnate_settings(v,settings)
        elif isinstance(v, str):
            for info,value in settings.items():
                v=v.replace(info, value) 
        new[k]=v
    return new

class DiscoveryWatcher:
    def __init__(self, directory,client,config):
        self._directory = directory
        self.config = config

        self.event_handler = PatternMatchingEventHandler(
            patterns=["*.json"],ignore_directories=True)
        self.event_handler.on_created = self.on_created
        self.event_handler.on_modified = self.on_modified

        self.observer = Observer()
        self.observer.schedule(self.event_handler, self._directory,
                               recursive=False)

        self.client = client
        self.advertise_data = {}

        for domain in self.config["domains"]:
            self.client.message_callback_add(domain+"/log/advertise/+", self.on_advertise)

        self.observer.start()
    
    def on_created(self,event):
        basename = os.path.basename(event.src_path)
        print("File {0} created, update firmware info.".format(basename))
        if basename=="home-assistant.json":
            self.send_HA_discovery()
 
    def on_modified(self,event):
        basename = os.path.basename(event.src_path)
        print("File {0} modified, update firmware info.".format(basename))
        if basename=="home-assistant.json":
            self.send_HA_discovery()

    def on_mqtt_connexion(self):
        if os.path.exists(os.path.join(self._directory,"home-assistant.json")):
            self.send_HA_discovery()

        for domain in self.config["domains"]:
            self.client.subscribe(domain+"/log/advertise/+")
            print("suscribed to: "+domain+"/log/advertise/+")


    def send_HA_discovery(self):
        self.ha_config = {}
        print("update Home Assistant discovery")
        json_path = os.path.join(self._directory,"home-assistant.json")
        if not os.path.exists(json_path):
            print("Error, {0} file does not exist".format(json_path))
        with open(json_path) as f:
            data = json.load(f)
            global_params = data["globals"]
            node_type_params = data["node_types"]
            nodes_params = data["devices"]

            for node_id, node_param in nodes_params.items():

                if not isinstance(node_param["node_type"], list):
                    node_param["node_type"] = [node_param["node_type"]]

                for node_type in node_param["node_type"]:
                    key = node_type+"_"+node_id
                    self.ha_config[key] = {}
                    self.ha_config[key]["message"] = {}

                    message = {}
                    
                    #Add globals settings
                    message.update(global_params)

                    #Add node_type settings
                    if (node_type in node_type_params):
                        message.update(node_type_params[node_type])

                    #Add device settings
                    message.update(node_param)

                    #Replace settings variable
                    device_id = node_param["device_id"] if "device_id" in node_param  else node_id
                    message = incarnate_settings(message,{"${device_id}":device_id})
                    message = incarnate_settings(message,{"${node_id}":node_id})

                    #Replace advertising data
                    if device_id in self.advertise_data:
                        if "device" not in message:
                            message["device"] = {}
                        message["device"].update(self.advertise_data[device_id])

                    if device_id == node_id:
                        topic = data["discovery_prefix"]+"/"+message["component"]+"/"+device_id+"/config"
                    else:
                        topic = data["discovery_prefix"]+"/"+message["component"]+"/"+device_id+"/"+node_id+"/config"

                    if "node_type" in message: del message["node_type"]
                    if "component" in message: del message["component"]
                    if "device_id" in message: del message["device_id"]

                    self.ha_config[key] = {"topic":topic,"message":message,"device_id":device_id}
                    print(" > config for "+key+" sent")

            #print(self.ha_config)

        for id,config in self.ha_config.items():
            #print(config["message"])
            self.client.publish(config["topic"], payload=json.dumps(config["message"]), qos=1, retain=True)
            
            #self.client.publish(config["topic"], payload=None, qos=1, retain=True)


    def refresh_HA_discovery(self,deviceId):
        keys = [key for key,config in self.ha_config.items() if config["device_id"]==deviceId]
        for key in keys:
            message = self.ha_config[key]["message"]
            topic = self.ha_config[key]["topic"]
            if "device" not in message:
                message["device"] = {}
            message["device"].update(self.advertise_data[deviceId])
            self.ha_config[key]["message"] = message
            self.client.publish(topic, payload=json.dumps(message), qos=1, retain=True)
            print(" > config for "+key+" sent")


    def on_advertise(self, client, userdata, msg):
        #print(msg.topic+" "+str(msg.payload))
        payload = msg.payload
        topic=  msg.topic.split("/") 
        if (len(payload) == 0 or topic[3] =="set"):
            return #empty message or set message
        if (len(topic) >= 5 and topic[4] =="set"):
            return #empty message or set message

        deviceId = topic[3]

        advertise_data = json.loads(payload)
        data = {}
        if "fw" in advertise_data:
            data["model"] = advertise_data["fw"]["name"]
            data["sw_version"] = advertise_data["fw"]["version"]
        if "implementation" in advertise_data:
            data["model"] += " ("+advertise_data["implementation"]["device"]+")"
            data["sw_version"] += " ("+advertise_data["implementation"]["version"]+")"
        if "mac" in advertise_data:
            data["connections"] =  [["mac":advertise_data["mac"]]]

        self.advertise_data[deviceId] = data

        print("New data received from "+deviceId+" publish discovery")
        self.refresh_HA_discovery(deviceId)




