from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import os, json
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
    def __init__(self, directory,client):
        self._directory = directory

        self.event_handler = PatternMatchingEventHandler(
            patterns=["*.json"],ignore_directories=True)
        self.event_handler.on_created = self.on_created
        self.event_handler.on_modified = self.on_modified

        self.observer = Observer()
        self.observer.schedule(self.event_handler, self._directory,
                               recursive=False)

        self.observer.start()

        self.client = client

        if os.path.exists(os.path.join(self._directory,"home-assistant.json")):
            self.send_HA_discovery()

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

                    if device_id == node_id:
                        topic = data["discovery_prefix"]+"/"+message["component"]+"/"+device_id+"/config"
                    else:
                        topic = data["discovery_prefix"]+"/"+message["component"]+"/"+device_id+"/"+node_id+"/config"

                    if "node_type" in message: del message["node_type"]
                    if "component" in message: del message["component"]
                    if "device_id" in message: del message["device_id"]

                    self.ha_config[key] = {"topic":topic,"message":message}
                    

            #print(self.ha_config)

        for id,config in self.ha_config.items():
            self.client.publish(config["topic"], payload=json.dumps(config["message"]), qos=1, retain=True)
            #self.client.publish(config["topic"], payload=None, qos=1, retain=True)






