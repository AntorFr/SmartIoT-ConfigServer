
import re, sys, os
import base64, sys, math
from hashlib import md5

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler


class FirmwareWatcher:
    def __init__(self, directory):
        self._directory = directory
        self.firmwares = {}

        #self.read_firmware_folder()

        self.event_handler = PatternMatchingEventHandler(
            patterns=["*.bin"],ignore_directories=True)
        self.event_handler.on_created = self.on_created
        self.event_handler.on_deleted = self.on_deleted
        self.event_handler.on_modified = self.on_modified
        self.event_handler.on_moved = self.on_moved

        self.observer = Observer()
        self.observer.schedule(self.event_handler, self._directory,
                               recursive=False)

        self.observer.start() 

    def on_created(self,event):
        print("File {0} created, update firmware info.".format(event.src_path))
        self._update_firmware_info(event.src_path) 

    def on_modified(self,event):
        print("File {0} modified, update firmware info.".format(event.src_path))
        self._update_firmware_info(event.src_path) 

    def on_deleted(self,event):
        print("File {0} deleted, update firmware info.".format(event.src_path))
        #todo delete file from firmware list
        self._remove_firmware_info(event.src_path) 
        #self._read_firmware_folder() 

    def on_moved(self,event):
        print("File {0} moved, update firmware info.".format(event.src_path))
        self._read_firmware_folder()  

    @staticmethod
    def version_toint(version):
        v = version.split(".")
        return sum([int(val)*(100**int(3-idx)) for idx, val in enumerate(v)])

    @staticmethod
    def get_firmware_data(path):
        try:
            firmware_file = open(path, "rb")
        except Exception as err:
            print("Error: {0}".format(err))

        firmware_binary = firmware_file.read()
        firmware_file.close()
        firmware = bytearray()
        firmware.extend(firmware_binary)
        return firmware

    def _remove_firmware_info(self,path):
        for name, firmware in list(self.firmwares.items()):
            if (path == firmware["path"]):
                self.remove(firmware)
                self.firmwares.pop(name)
            


    def _update_firmware_info(self,path):
        firmware = {}

        regex_SmartIoT = re.compile(b"\x25\x48\x4f\x4d\x49\x45\x5f\x45\x53\x50\x38\x32\x36\x36\x5f\x46\x57\x25")
        regex_name = re.compile(b"\xbf\x84\xe4\x13\x54(.+)\x93\x44\x6b\xa7\x75")
        regex_version = re.compile(b"\x6a\x3f\x3e\x0e\xe1(.+)\xb0\x30\x48\xd4\x1a")
        regex_brand = re.compile(b"\xfb\x2a\xf5\x68\xc0(.+)\x6e\x2f\x0f\xeb\x2d")

        try:
            firmware_file = open(path, "rb")
        except Exception as err:
            print("Error: {0}".format(err))
            return

        firmware_binary = firmware_file.read()
        firmware_file.close()

        # read the contents of firmware into buffer
        regex_name_result = regex_name.search(firmware_binary)
        regex_version_result = regex_version.search(firmware_binary)

        if not regex_SmartIoT.search(firmware_binary) or not regex_name_result or not regex_version_result:
            print(path + "file is not a valid SmartIot firmware")
            return 

        regex_brand_result = regex_brand.search(firmware_binary)
        name = regex_name_result.group(1).decode()
        version = regex_version_result.group(1).decode()
        brand = regex_brand_result.group(1).decode() if regex_brand_result else "SmartIot"

        fwbytear = bytearray()
        fwbytear.extend(firmware_binary)

        firmware["name"] = name
        firmware["version"] = version
        firmware["brand"] = brand
        firmware["int_version"] = self.version_toint(version)
        firmware["path"] = path
        firmware["md5"] = md5(fwbytear).hexdigest()

        if (firmware["name"] not in self.firmwares) or \
        ((self.firmwares[firmware["name"]]["int_version"]<firmware["int_version"])):
                #TODO if old firmware published, remove it
                firmware["published"] = False
                self.firmwares[firmware["name"]] = firmware
                print(path + " file included in firmware list")
                self.add(firmware)
                return True
        else:
            print(path + " file outdated, not included  in firmware list")
            return False

    def _read_firmware_folder(self):
        for filename in os.listdir(self._directory):
            if (filename.endswith(".bin")):
                self._update_firmware_info(os.path.join(self._directory, filename))



        

