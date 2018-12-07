#!/usr/bin/env python
#
# This file is licensed under the terms of the GPL, Version 3
#
# Copyright 2018 Tamas Kinsztler <https://github.com/humpedli>

__author__ = "Tamas Kinsztler"
__copyright__ = "Copyright (C) Tamas Kinsztler"
__license__ = "GPLv3"
__version__ = "1.0"

import os
import logging
import signal
import socket
import time
import sys
import paho.mqtt.client as mqtt
import argparse
import ConfigParser
import RPi.GPIO as GPIO
import setproctitle
from datetime import datetime, timedelta

parser = argparse.ArgumentParser( formatter_class=argparse.RawDescriptionHelpFormatter, description='''sends data to GPIO ports from mqtt-broker''')
parser.add_argument('config_file', metavar="<config_file>", help="file with configuration")
args = parser.parse_args()

# Read and parse config file
config = ConfigParser.RawConfigParser()
config.read(args.config_file)

# [mqtt]
MQTT_HOST = config.get("mqtt", "host")
MQTT_PORT = config.getint("mqtt", "port")
STATUSTOPIC = config.get("mqtt", "statustopic")
POLLINTERVAL = config.getint("mqtt", "pollinterval")

# [log]
LOGFILE = config.get("log", "logfile")
VERBOSE = config.get("log", "verbose")

# [gpios]
section_name = "gpios"
gpios = {}
for name, value in config.items(section_name):
    gpios[name] = int(value)

# compose MQTT client ID from appname and PID
APPNAME = "mqtt-gpio-trigger"
setproctitle.setproctitle(APPNAME)
MQTT_CLIENT_ID = APPNAME + "[_%d]" % os.getpid()
MQTTC = mqtt.Client(MQTT_CLIENT_ID)

# init logging 
LOGFORMAT = '%(asctime)-15s %(message)s'
if VERBOSE:
    logging.basicConfig(filename=LOGFILE, format=LOGFORMAT, level=logging.DEBUG)
else:
    logging.basicConfig(filename=LOGFILE, format=LOGFORMAT, level=logging.INFO)

logging.info("Starting " + APPNAME)
if VERBOSE:
    logging.info("INFO MODE")
else:
    logging.debug("DEBUG MODE")

### MQTT Callback handler ###

# MQTT on message handler
def on_message(self, obj, msg):
	try:
		logging.debug(("GPIO %s : %s") % (msg.topic, msg.payload))
		if msg.payload=='ON':
			GPIO.output(gpios[msg.topic],GPIO.LOW)
			self.publish(("%s/status") % (msg.topic), "ON")
		if msg.payload=='OFF':
			GPIO.output(gpios[msg.topic],GPIO.HIGH)
			self.publish(("%s/status") % (msg.topic), "OFF")

	except ow.exUnknownGPIO:
		logging.info("Threw an unknown GPIO exception for device %s. Continuing", msg.topic)

# MQTT: message is published
def on_mqtt_publish(mosq, obj, mid):
    logging.debug("MID " + str(mid) + " published.")

# MQTT: connection to broker 
# client has received a CONNACK message from broker
# return code:
#   0: Success                                                      -> Set LASTWILL 
#   1: Refused - unacceptable protocol version->EXIT
#   2: Refused - identifier rejected                                -> EXIT 
#   3: Refused - server unavailable                                 -> RETRY
#   4: Refused - bad user name or password (MQTT v3.1 broker only)  -> EXIT
#   5: Refused - not authorised (MQTT v3.1 broker only)             -> EXIT
def on_mqtt_connect(self, mosq, obj, return_code):    
    logging.debug("on_connect return_code: " + str(return_code))
    if return_code == 0:
        logging.info("Connected to %s:%s", MQTT_HOST, MQTT_PORT)
        # set Lastwill 
        self.publish(STATUSTOPIC, "1 - connected", retain=True)
        # process_connection()
    elif return_code == 1:
        logging.info("Connection refused - unacceptable protocol version")
        cleanup()
    elif return_code == 2:
        logging.info("Connection refused - identifier rejected")
        cleanup()
    elif return_code == 3:
        logging.info("Connection refused - server unavailable")
        logging.info("Retrying in 10 seconds")
        time.sleep(10)
    elif return_code == 4:
        logging.info("Connection refused - bad user name or password")
        cleanup()
    elif return_code == 5:
        logging.info("Connection refused - not authorised")
        cleanup()
    else:
        logging.warning("Something went wrong. RC:" + str(return_code))
        cleanup()

# MQTT: disconnected from broker
def on_mqtt_disconnect(mosq, obj, return_code):
    if return_code == 0:
        logging.info("Clean disconnection")
    else:
        logging.info("Unexpected disconnection. Reconnecting in 5 seconds")
        logging.debug("return_code: %s", return_code)
        time.sleep(5)

# MQTT: debug log
def on_mqtt_log(mosq, obj, level, string):
    if VERBOSE:
        logging.debug(string)

### END of MQTT Callback handler ###

# clean disconnect on SIGTERM or SIGINT. 
def cleanup(signum, frame):
    logging.info("Disconnecting from broker")
    # Publish a retained message to state that this client is offline
    MQTTC.publish(STATUSTOPIC, "0 - DISCONNECT", retain=True)
    MQTTC.disconnect()
    MQTTC.loop_stop()
    GPIO.cleanup()
    logging.info("Exiting on signal %d", signum)
    sys.exit(signum)


# init connection to MQTT broker
def mqtt_connect():
    logging.debug("Connecting to %s:%s", MQTT_HOST, MQTT_PORT)

    # Set the last will before connecting
    MQTTC.will_set(STATUSTOPIC, "0 - LASTWILL", qos=0, retain=True)
    result = MQTTC.connect(MQTT_HOST, MQTT_PORT, 60)
    if result != 0:
        logging.info("Connection failed with error code %s. Retrying", result)
        time.sleep(10)
        mqtt_connect()

    for GPIO_TOPIC, GPIO_PORT in gpios.items():
        MQTTC.subscribe(GPIO_TOPIC, 0)

    # Define callbacks
    MQTTC.on_connect = on_mqtt_connect
    MQTTC.on_disconnect = on_mqtt_disconnect
    MQTTC.on_publish = on_mqtt_publish
    MQTTC.on_message = on_message
    MQTTC.on_log = on_mqtt_log
    MQTTC.loop_start()

# Main Loop
def main_loop():
    logging.debug(("MQTT broker    : %s") % (MQTT_HOST))
    logging.debug(("  port         : %s") % (str(MQTT_PORT)))
    logging.debug(("statustopic    : %s") % (str(STATUSTOPIC)))
    logging.debug(("GPIOs        : %s") % (len(gpios)))

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    for GPIO_TOPIC, GPIO_PORT in gpios.items():
        logging.debug(("  %s : %s") % (GPIO_TOPIC, GPIO_PORT))
        GPIO.setup(GPIO_PORT, GPIO.OUT, initial=GPIO.HIGH)

    # Connect to the broker and enter the main loop
    mqtt_connect()

    while True:
        # iterate over all GPIOs
        for GPIO_TOPIC, GPIO_PORT in gpios.items():
            logging.debug(("Querying %s : %s") % (GPIO_TOPIC, GPIO_PORT))
            try:
                status = int(GPIO.input(GPIO_PORT))
                logging.debug(("GPIO %s : %s") % (GPIO_PORT, status))
                MQTTC.publish(("%s/status") % (GPIO_TOPIC), "ON" if status == 0 else "OFF")
            except ow.Error:
                logging.info("Threw an unknown GPIO exception for device %s - %s. Continuing", GPIO_TOPIC, GPIO_PORT)
                continue
            
            time.sleep(float(POLLINTERVAL) / len(gpios))

# Use the signal module to handle signals
signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

# start main loop
try:
    main_loop()
except KeyboardInterrupt:
    logging.info("Interrupted by keypress")
    sys.exit(0)