# Copyright (c) 2013 Calin Crisan
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import asyncio
import datetime
import json
import logging
import os
import socket
from datetime import datetime
from io import BytesIO

import httpx
from tornado import queues
from tornado.ioloop import IOLoop

from motioneye import config, settings
from motioneye.controls import tzctl

class TelegramHandler:

    _instance = None

    def __init__(self):
        if TelegramHandler._instance != None:
            raise Exception("TelegramHandler instance exists already!")
        self.queue = queues.Queue()
        self.events = self.Event()
        TelegramHandler._instance = self

    @staticmethod
    def get_instance():
        if TelegramHandler._instance is None:
           TelegramHandler()
        return TelegramHandler._instance

    def start(self):
        logging.debug("starting media_handle_loop")
        io_loop = IOLoop.current()
        io_loop.add_callback(self.media_handle_loop)

    async def add_media(self, media):
        if (media["event"] == "picture_save"):
            logging.debug(f"adding new media: {media['file_name']}")
        await self.queue.put(media)

    async def media_handle_loop(self):
        logging.debug("started media_handle_loop")

        while True:

            # get new item from queue and initialize needed vars
            item = await self.queue.get()
            camera_id = item["camera_id"]
            event = item["event"]
            event_id = item["event_id"]
            moment = item["moment"]
            camera_config = config.get_camera(camera_id)
            max_pictures = camera_config["@telegram_notifications_max_pictures"]

            if event == "picture_save":
                self.events.add_event(item)

            elif event == "stop":
                try:
                    files = self.events.get_files(event_id, max_pictures) 
                    num_files = len(files)
                    logging.debug(f"[{event_id}] got files: {num_files}, limiting to { num_files if num_files <= max_pictures else max_pictures} per settings")

                    msg_data = self.prepare_message(camera_config, files, event_id, moment)

                    response = await self.send_message(msg_data)
                    
                    self.check_response(response)

                    self.events.do_stop(event_id)

                    self.queue.task_done()

                except KeyError as e:
                    # no such key exists, happens when "stop" event is received before "picture_save" one
                    logging.warning(f"[{event_id}] - readding item, exception: {repr(e)}")

                    self.queue.task_done()

                    # wait before another attempt to "stop" this specific event  
                    await asyncio.sleep(5)

                    # and readd item
                    await self.queue.put(item)

                except Exception as e:
                    logging.exception(repr(e))
                    
    def prepare_message(self, camera_config, files, event_id = None, moment = None, test = False):

        logging.debug("creating telegram message")
        api_key = camera_config["@telegram_notifications_api"]
        chat_id = camera_config["@telegram_notifications_chat_id"]
        telegram_url = f"https://api.telegram.org/bot{api_key}/sendMediaGroup"

        # as per telegram bot api documentation - 10 MB
        TELEGRAM_API_PHOTO_SIZE_LIMIT = 10 * 1024 * 1024

        def check_file(file):
            status = False
            try:
                size = os.path.getsize(file)
                # todo choose right unit KB, MB
                logging.debug(f"checking file: {file} - {round(size / (1024*1024), 1)} [MB]")
            
                if(size <= TELEGRAM_API_PHOTO_SIZE_LIMIT):
                    status = True
                else:
                    logging.warning(f"file exceeds max size limit: {file} - {round(size / (1024*1024), 1)} > {round(TELEGRAM_API_PHOTO_SIZE_LIMIT / (1024*1024), 1)} [MB]")

            except Exception as e:
                logging.exception(repr(e))
            
            finally:
                return status

        
        # check files for existence and their size 
        _files = [file for file in files if check_file(file)]

        # append placeholder image to send with telegram api test, nice pic btw :)
        if test:
            _files.append(settings.STATIC_PATH + "/img/motioneye-icon.jpg")

        bytes = {}
        media = []
        for i, img in enumerate(_files):
            with BytesIO() as output, open(img, "+rb") as fh:
                output.seek(0)
                name = f"img-{i}"
                bytes[name] = fh.read()
                media.append(dict(type="photo", media=f"attach://{name}"))

        text = ""

        if not test:
            # set message strings        
            timezone = tzctl.get_time_zone() if settings.LOCAL_TIME_FILE else "local time"
            camera_name = camera_config["camera_name"]
            message = f"Motion has been detected by: {camera_name} / {socket.gethostname()}\n"
            message += f"At: {datetime.fromisoformat(moment).strftime('%Y-%m-%d %H:%M:%S')} / {timezone}"
            # additional debug information
            if (settings.LOG_LEVEL == logging.DEBUG):
                message += f"\nEvent_id: {event_id}\n"

            if (len(media) > 0):
                # apply caption on the first image 
                media[0]["caption"] = message
            else:
                # this is not a test and there are no pictures (max_pictures set to 0) api url change is needed
                telegram_url = f"https://api.telegram.org/bot{api_key}/sendMessage"
                text = message
                media = ""
                bytes = ""
        else:
            # telegram api test case
            media[0]["caption"] = 'This is a test of motionEye\'s telegram messaging'
        
        return {"chat_id" : chat_id, "text" : text, "media": media, "files": bytes, "url" : telegram_url} 

    async def send_message(self, msg_data):

        try:
            # used httpx library, imho it's much simplier
            async with httpx.AsyncClient() as client:
                timeout = httpx.Timeout(float(settings.REMOTE_REQUEST_TIMEOUT))
                response = await client.post(msg_data["url"], 
                                            data={"chat_id": msg_data["chat_id"], "text" : msg_data["text"], "media": json.dumps(msg_data["media"])}, 
                                            files=msg_data["files"], 
                                            timeout=timeout)
                return response.json()
            
        except Exception as err:
            # sometimes telegram bot api returns invalid response however, the message is delivered...
            # in such case, description is set to None : None
            return {"ok" : False, "description" : err}

    async def send_test_message(self, api_key, chat_id):
        
        message = self.prepare_message({"@telegram_notifications_api" : api_key, "@telegram_notifications_chat_id" : chat_id }, files = [], test = True )
        response = await self.send_message(message)

        if not self.check_response(response):
            raise Exception(response)
    
    def check_response(self, response):
        # perform parsing of response data, only informational purposes
        if response["ok"]:
            logging.info("telegram succesfully sent")
            return True
        else:
            # not acting on error, logging only
            logging.error(f"failed to send telegram: \"{response}\"")
            return False

    class Event():
        
        def __init__(self) -> None:
            self.events = dict()

        def add_event(self, item):
            event_id = item["event_id"]
            file_name = item["file_name"]
            moment = item["moment"]

            if not self.event_exist(event_id):
                self.events[event_id] = {"start": moment, "files": [file_name], "stop" : False}

            # append only unique files to the list 
            elif not self.file_exist(event_id, file_name):
                if (self.is_stopped(event_id)):
                    logging.warning(f"[{event_id}] Attempt to add picture after STOP event!!")
                else:
                    self.add_new_file(event_id, file_name)

        def add_new_file(self, event_id, file_name):
            self.events[event_id]["files"].append(file_name)

        def get_files(self, event_id, limit):
            return self.events[event_id]["files"][0:limit]

        def file_exist(self, event_id, file_name):
            return file_name in self.events[event_id]["files"]

        def event_exist(self, event_id):
            return event_id in self.events

        def is_stopped(self, event_id):
            return self.events[event_id]["stop"]

        def do_stop(self, event_id):
            self.events[event_id]["stop"] = True
            self.events[event_id]["files"] = []