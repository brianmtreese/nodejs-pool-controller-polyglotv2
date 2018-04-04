#!/usr/bin/env python3

import polyinterface
import sys
import time
import json
import requests

LOGGER = polyinterface.LOGGER

_ISY_BOOL_UOM = 2 # Used for reporting status values for Controller node
_ISY_INDEX_UOM = 25 # Index UOM for custom states (must match editor/NLS in profile):
_ISY_TEMP_F_UOM = 17 # UOM for temperatures

# CONVERT TO CONFIGURATION DATA
_BASE_URL = 'http://localhost:3000'
_CIRCUITS_NOT_USED = ['9','10','11','12','13','14','15','16','17','18','19','20']
_POOL_CIRCUIT_ID = 1
_SPA_CIRCUIT_ID = 6

# Get all data from nodejs pool controller api
allData = requests.get(url='{}/all'.format(_BASE_URL))
allDataJson = allData.json()

# Get circuits in use
circuits = allDataJson['circuits']
circuitsNotUsed = _CIRCUITS_NOT_USED
for key in circuits.keys():
    for circuitNotUsed in circuitsNotUsed:
        if key == circuitNotUsed:
            del circuits[key]

# Get temperature data
temperatureData = requests.get(url='{}/temperatures'.format(_BASE_URL))
temperatureDataJson = temperatureData.json() 

with open('server.json') as data:
    SERVERDATA = json.load(data)
    data.close()
try:
    VERSION = SERVERDATA['credits'][0]['version']
except (KeyError, ValueError):
    LOGGER.info('Version not found in server.json.')
    VERSION = '0.0.0'

class Controller(polyinterface.Controller):
    
    id = 'CONTROLLER'
    
    def __init__(self, polyglot):
        super(Controller, self).__init__(polyglot)
        self.name = 'Pool Controller'
        
    def start(self):
        LOGGER.info('Starting Pool Controller Polyglot v2 NodeServer version {}'.format(VERSION))
        self.discover()
        
    def shortPoll(self):
        for node in self.nodes:
            self.nodes[node].update()
    
    def discover(self, command = None):
        
        # Discover Pool Circuit Nodes
        LOGGER.info('Found {} Circuits'.format(len(circuits)))
        
        for circuit in sorted(circuits, key=int):
            id = circuit
            number = circuit
            address = circuits[circuit].get('numberStr')
            name = circuits[circuit].get('friendlyName').title()
            status = circuits[circuit].get('status')
            
            if address not in self.nodes:
                self.addNode(Circuit(self, self.address, id, address, name, status, number))
            else:
                LOGGER.info('Circuit {} already configured.'.format(name))
        
        # Add Pool and Spa Temperature Nodes
        temperatures = ['spa','pool']
              
        for temperature in temperatures:
            id = temperature
            address = ('{}_heat'.format(temperature))
            name = ('{} Heat'.format(temperature)).title()
            type = temperature
            
            if address not in self.nodes:
                self.addNode(Temperature(self, self.address, id, address, name, type))
            else:
                LOGGER.info('Temperature {} already configured.'.format(name))
    
    def update(self, report=True):
        
        # Get node js pool controller status
        controllerData = requests.get(url='{}/all'.format(_BASE_URL))
        if controllerData.status_code == 200:
            self.setDriver('GV0', 1, report)
        else:
            self.setDriver('GV0', 0, report)    
        
        # Get temperatures      
        airTemp = temperatureDataJson['airTemp']
        poolTemp = temperatureDataJson['poolTemp']
        poolSetpoint = temperatureDataJson['poolSetPoint']
        spaTemp = temperatureDataJson['spaTemp']
        spaSetpoint = temperatureDataJson['spaSetPoint']
        
        # Get specific circuit statuses
        for circuit in circuits:
            circuitType = circuits[circuit].get('circuitFunction')
            if circuitType == 'Pool':
                status = circuits[circuit].get('status')
                self.setDriver('GV1', status, report)
            if circuitType == 'Spa':
                status = circuits[circuit].get('status')
                self.setDriver('GV4', status, report)

        # Update the controller node drivers
        self.setDriver('CLITEMP', airTemp, report)
        self.setDriver('GV2', poolTemp, report)
        self.setDriver('GV3', poolSetpoint, report)
        self.setDriver('GV5', spaTemp, report)
        self.setDriver('GV6', spaSetpoint, report)
    
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': _ISY_BOOL_UOM},
        {'driver': 'GV0', 'value': 0, 'uom': _ISY_BOOL_UOM},        
        {'driver': 'CLITEMP', 'value': 0, 'uom': _ISY_TEMP_F_UOM},
        {'driver': 'GV1', 'value': 0, 'uom': _ISY_INDEX_UOM},
        {'driver': 'GV2', 'value': 0, 'uom': _ISY_TEMP_F_UOM},
        {'driver': 'GV3', 'value': 0, 'uom': _ISY_TEMP_F_UOM},
        {'driver': 'GV4', 'value': 0, 'uom': _ISY_INDEX_UOM},
        {'driver': 'GV5', 'value': 0, 'uom': _ISY_TEMP_F_UOM},
        {'driver': 'GV6', 'value': 0, 'uom': _ISY_TEMP_F_UOM}
    ]

    commands = {
        'DISCOVER': discover,
        'QUERY': update
    }
    
class Circuit(polyinterface.Node):
    
    id = 'CIRCUIT'
    
    def __init__(self, controller, primary, id, address, name, status, number):
        super(Circuit, self).__init__(controller, primary, address, name)
        self.name = name
        self.status = status
        self.number = number

    def start(self):
        self.query()
        LOGGER.info('{} ready!'.format(self.name))
    
    def update(self):
        self.get_status()
            
    def query(self, command=None):
        self.update()
        self.reportDrivers()
        
    def get_status(self, report=True):
        circuitData = requests.get(url='{0}/circuit/{1}'.format(_BASE_URL, self.number))
        circuitDataJson = circuitData.json()
        status = circuitDataJson['status']
        self.setDriver('ST', status, report)
        
    def cmd_don(self, command):
        requests.get(url='{0}/circuit/{1}/toggle'.format(_BASE_URL, self.number))
        self.update()
        print (self.name + ' turned on')

    def cmd_dof(self, command):
        requests.get(url='{0}/circuit/{1}/toggle'.format(_BASE_URL, self.number))
        self.update()
        print (self.name + ' turned off')
        
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': _ISY_INDEX_UOM}
    ]
    commands = {
        'DON': cmd_don,
        'DOF': cmd_dof
    }

class Temperature(polyinterface.Node):

    id = 'TEMPERATURE'
    
    def __init__(self, controller, primary, id, address, name, type):
        super(Temperature, self).__init__(controller, primary, address, name)
        self.name = name
        self.type = type
        
    def update(self):
        self.get_status()
        
    def query(self, command=None):
        self.update()
        self.reportDrivers()
        
    def get_status(self, report=True):
        if self.type == 'spa':
            status = temperatureDataJson['spaHeatMode']
            temperature = temperatureDataJson['spaTemp']
            setPoint = temperatureDataJson['spaSetPoint']
        else:
            status = temperatureDataJson['poolHeatMode']
            temperature = temperatureDataJson['poolTemp']
            setPoint = temperatureDataJson['poolSetPoint']
            
        self.setDriver('ST', status, report)
        self.setDriver('CLISPH', setPoint, report)
        self.setDriver('CLITEMP', temperature, report)
        
    def cmd_don(self, command):
        if self.name == 'spa':
            status = temperatureDataJson['spaHeatMode']
            if status == 0:
                requests.get(url='{}/spaheat/mode/1'.format(_BASE_URL))
                
        else:
            status = temperatureDataJson['poolHeatMode']
            if status == 0:
                requests.get(url='{}/poolheat/mode/1'.format(_BASE_URL))

    def cmd_dof(self, command):
        if self.name == 'spa':
            status = temperatureDataJson['spaHeatMode']
            if status == 1:
                requests.get(url='{}/spaheat/mode/0'.format(_BASE_URL))
                
        else:
            status = temperatureDataJson['poolHeatMode']
            if status == 1:
                requests.get(url='{}/poolheat/mode/0'.format(_BASE_URL))

    def cmd_set_temp(self, command):        
        value = int(command.get('value'))
        if self.name == 'spa':
            requests.get(url='{0}/spaheat/setpoint/{1}'.format(_BASE_URL, value))
                
        else:
            requests.get(url='{0}/poolheat/setpoint/{1}'.format(_BASE_URL, value))

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': _ISY_INDEX_UOM},
        {'driver': 'CLISPH', 'value': 0, 'uom': _ISY_TEMP_F_UOM},
        {'driver': 'CLITEMP', 'value': 0, 'uom': _ISY_TEMP_F_UOM}
    ]
    commands = {
        'DON': cmd_don,
        'DOF': cmd_dof,
        'SET_TEMP': cmd_set_temp
    }


if __name__ == '__main__':
    try:
        polyglot = polyinterface.Interface('Pool')
        polyglot.start()
        control = Controller(polyglot)
        control.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)