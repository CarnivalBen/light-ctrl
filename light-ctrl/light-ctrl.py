import RPi.GPIO as GPIO
import json
from flask import Flask
from time import sleep
import requests
import threading

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

with open('light-ctrl.conf') as f:
    cfg = json.load(f,)

switch_override = []
sensor_state = {}


def fetch_sensor_state(sensors):
    if type(sensors) == str or type(sensors) == unicode:
        print("State of single sensor %s is %s" %(sensors,sensor_state[sensors]))
        return sensor_state[sensors]

    elif type(sensors) is list:
        for name in sensors:
            print("State of grouped sensor %s is %s" %(name,sensor_state[name]))
            if sensor_state[name] == 1:
                return 1

    else:
        print("Invalid sensor specification: %s [%s]" %(sensors,type(sensors)))


    return 0


def apply_rules():

    # build list of switches to calculate the new states
    switch_state = {}
    for switch in cfg["switches"]:
        switch_state[switch["name"]] = 0

    # apply any matching rules to the new sensor states
    for rule in cfg["rules"]:
        rule_state = 1
        for rule_sensor in rule["sensors"]:
            rule_sensor_state = fetch_sensor_state(rule_sensor)
            if rule_sensor_state == 0:
                rule_state = 0                
                break
        
        if rule_state == 1:
            print("Rule %s has been activated." %(rule["name"]))
            for rule_switch in rule["switches"]:
                switch_state[rule_switch] = 1

    # apply any overrides
    for overridden_switch in switch_override:
        switch_state[overridden_switch] = 1

    # set switch to new states
    for switch in cfg["switches"]:
        GPIO.output(switch["pin"], switch_state[switch["name"]])


def update_sensor(sensor_name, new_state, call_apply_rules = True):    
    print("Update sensor %s to %s" %(sensor_name, new_state))
    # validate input
    if new_state != 0 and new_state != 1:
        print("State of %s must be either 0 or 1, not [%s]" %(sensor_name, new_state))
        return

    # find sensor
    sensor = next((s for s in cfg["sensors"] if s["name"] == sensor_name), None)
    if sensor is None:
        print("Cannot apply new state to unknown sensor %s" %(sensor_name))
        return

    # false alarm, state has not changed.    
    if sensor_state[sensor["name"]] == new_state:
        print("Sensor %s state has not changed." %(sensor["name"]))
        return;
            
    print("Applying new state to %s [%d]" %(sensor_name, new_state))
    sensor_state[sensor["name"]] = new_state

    # if sensor has a pin, then send the new state to all other nodes.
    if "pin" in sensor:
        for node in cfg["nodes"]:
            try:
                req = requests.post("%s/%s/%d" %(node["endpoint"], sensor["name"], new_state))
                if req.status_code != 200:
                    print("Failed to send new state to node %s, status code %d" %(node["name"], req.status_code))

            except:
                print("Node %s not responding." %(node["name"]))
    
    if call_apply_rules:
        apply_rules()



def sensor_callback(channel):
    sleep(0.2)
    print("SENSOR [{0}] = [{1}]".format(channel, GPIO.input(channel)))
    for sensor in cfg["sensors"]:
        if "pin" in sensor and channel == sensor["pin"]:
            update_sensor(sensor["name"], GPIO.input(sensor["pin"]))


# validate config
if "switches" not in cfg:
    print("Config error: Missing switches list.")
    quit()

if "sensors" not in cfg:
    print("Config error: Missing sensors list.")
    quit()

if "nodes" not in cfg:
    cfg["nodes"] = []

if "rules" not in cfg:
    cfg["rules"] = []

for switch in cfg["switches"]:
    if "name" not in switch:
        print("Config error: Switch with no name.")
        quit()

    if "pin" not in switch:
        print("Config error: switch with no pin.")
        quit()

    if type(switch["name"]) != str and type(switch["name"]) != unicode:
        print("Config error: Switch name must be string, not %s." %(type(switch["name"])))
        quit()

    if type(switch["pin"]) != int:
        print("Config error: Switch %s must have integer pin." %(switch["name"]))
        quit()


for switch in cfg["switches"]:
    print("Configuring %s as physical switch on pin %d" %(switch["name"], switch["pin"]))
    GPIO.setup(switch["pin"], GPIO.OUT)

for sensor in cfg["sensors"]:
    sensor_state[sensor["name"]] = 0
    if "pin" in sensor:
        print("Configuring %s as physical sensor on pin %d" %(sensor["name"], sensor["pin"]))
        GPIO.setup(sensor["pin"], GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
        GPIO.add_event_detect(sensor["pin"], GPIO.BOTH, callback=sensor_callback, bouncetime=200)

sleep(0.3)
for switch in cfg["switches"]:
    GPIO.output(switch["pin"], 0)


refresh_counter = 2
def refresh():
    global refresh_counter

    try:
        refresh_counter -= 1
        if refresh_counter > 0:        
            return
        refresh_counter = 30

        for sensor in cfg["sensors"]:
            if "pin" in sensor:
                update_sensor(sensor["name"], GPIO.input(sensor["pin"]), False)
            
            else:
                for node in cfg["nodes"]:
                    try:
                        req = requests.get("%s/%s/state" %(node["endpoint"], sensor["name"]))
                        if req.status_code == 200:
                            update_sensor(sensor["name"], req.text, False)

                    except:
                        print("Node %s not responding." %(node["name"]))

        apply_rules()  
    finally:
        t = threading.Timer(2, refresh)
        t.setDaemon(True)
        t.start()

refresh()

app = Flask(__name__)

def override_switch(switch_name, state):
    if not state and switch_name in switch_override:
        print("Cancelling %s override." %(switch_name))
        switch_override.remove(switch_name)
    elif state and switch_name not in switch_override:
        print("Activating %s override." %(switch_name))
        switch_override.append(switch_name)

@app.route('/<switch_name>/on', methods=["POST"])
def switch_on(switch_name):
    for switch in cfg["switches"]:
        if switch["name"] == switch_name:
            override_switch(switch["name"], True)
            apply_rules()
            return "Switch {0} override activated.".format(switch["name"])

    return 'No action'

@app.route('/<switch_name>/off', methods=["POST"])
def switch_off(switch_name):
    for switch in cfg["switches"]:
        if switch["name"] == switch_name:
            override_switch(switch["name"], False)
            GPIO.output(switch["pin"], 0)
            sleep(0.25)
            apply_rules()
            return "Switch {0} override cancelled.".format(switch["name"])

    return 'No action'

@app.route('/<sensor_name>/state', methods=["GET"])
def get_sensor_state(sensor_name):
    for sensor in cfg["sensors"]:
        if "pin" in sensor and sensor["name"] == sensor_name:
            return str(sensor_state[sensor["name"]])
    return "Sensor not here.", 404

@app.route('/<sensor_name>/<int:state>', methods=["POST"])
def set_sensor_state(sensor_name, state):
    if state != 1 and state != 0:
        return "Invalid sensor state."

    for sensor in cfg["sensors"]:
        if sensor["name"] == sensor_name:
           update_sensor(sensor["name"], state)
           return "Updated sensor %s to %d." %(sensor["name"], state)
    return "Sensor %s was not found." %(sensor_name)
    

app.run(host='0.0.0.0', port=8090)