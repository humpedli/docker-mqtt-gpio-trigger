# MQTT GPIO Trigger with Docker 

This script listens for messages on MQTT broker which are related to switch GPIO pins on Raspberry.

A running mqtt-broker (e.g: [mosquitto](https://mosquitto.org)) are required to use this deamon.

**This container is designed for Raspberry Pi 3 (armv7hf)**


## Run with docker

Don't forget to create configuration file first (there is a sample in the repository), then attach the file as a volume like examples below.

```
docker run --name=mqtt-gpio-trigger \
  --restart=always \
  --network=host \
  --device=/dev/gpiomem \
  -v <path_to_config>/config.cfg:/usr/src/app/config.cfg \
  -v /etc/localtime:/etc/localtime:ro \
  -d humpedli/docker-mqtt-gpio-trigger
```


## Run with docker-compose

```
version: '3'
services:
  mqtt-gpio-trigger:
    container_name: "mqtt-gpio-trigger"
    image: "humpedli/docker-mqtt-gpio-trigger"
    devices:
      - "/dev/gpiomem:/dev/gpiomem"
    volumes:
      - "<path_to_config>/config.cfg:/usr/src/app/config.cfg"
      - "/etc/localtime:/etc/localtime:ro"
    network_mode: host
    restart: "always"
```


## Configuration file

a self explaining sample configuration file is included 

```
# sample configuration 
 
# MQTT broker related config
[mqtt]
host = 127.0.0.1
port = 1883

# polling interval for gpio status reports
# status report topic depends on your [gpios] configuration
# in current example topics are: switch/lamp1/status and switch/lamp2/status
pollinterval = 30

# topic for script status messages
statustopic = mqtt-gpio-trigger/status 

[log]
verbose = true
logfile = /var/log/onewire-to-mqtt.log

# list of gpio triggers (mqtt topics) and GPIO PIN numbers (BCM)
[gpios]
switch/lamp1 = 22
switch/lamp2 = 23
```