# Home lighting controller to work with Homebridge on a Raspberry Pi

## Python Dependencies

* RPi.GPIO - for interfacing with the Raspberry Pi GPIO pins
* Flask - for a simple web server to accept requests from homebridge to switch on/off the lights
* requests - to generate web requests to fetch the status of sensors on other nodes

## Configuration

Create a file in the working folder of the python script for the config named `light-ctrl.conf`.

```json
{
  "switches": [
    {
      "name": "gable",
      "pin": 16
    },
    {
      "name": "garden",
      "pin": 17
    },
    {
      "name": "wall",
      "pin": 18
    },
    {
      "name": "ambient",
      "pin": 22
    }
  ],
  "sensors": [
    {
      "name": "gable-pir",
      "pin": 27
    },
    {
      "name": "garden-left-pir",
      "pin": 24
    },
    {
      "name": "garden-right-pir",
      "pin": 25
    },
    {
      "name": "dusk-dawn",
      "pin": 26
    },
    {
      "name": "garage-pir"
    }
  ],
  "nodes": [
    {
      "name": "garage",
      "endpoint": "http://garage:8090"
    }
  ],
  "rules": [
    {
      "name": "night-ambient",
      "sensors": [
        "dusk-dawn"
      ],
      "switches": [
        "ambient"
      ]
    },
    {
      "name": "gable-activity",
      "sensors": [
        "dusk-dawn",
        "gable-pir"
      ],
      "switches": [
        "gable"
      ]
    },
    {
      "name": "garden-activity",
      "sensors": [
        "dusk-dawn",
        [
          "garden-left-pir",
          "garden-right-pir",
          "garage-pir"
        ]
      ],
      "switches": [
        "garden",
        "wall"
      ]
    }
  ]
}
```

### Switches

These are the light switches, requires a name and the BCM pin of the raspberry pi.

### Sensors

These are various sensors that the system needs to sense when to switch on/off the lights, for example a dusk til dawn sensor to switch on an ambient light in darkness.

### Nodes

Other Raspberry Pi devices on the network to share sensor statuses with.

### Rules

A list of scenarios that determine whether or not a light should be on or off depending on the state of the sensors, for example, a security light should only come on when the dust til dawn sensor is active, and the pir sensor detects movement.

All sensors listed under a rule need to be active for the light to illuminate, unless the sensors are listed in a sub list, in which case only one of the sub listed sensors need to be active.
