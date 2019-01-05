#!/usr/bin/env python3

import polyinterface
import sys
import time
import json
import requests
import copy

LOGGER = polyinterface.LOGGER

_ISY_BOOL_UOM = 2 # Used for reporting status values for Controller node
_ISY_INDEX_UOM = 25 # Index UOM for custom states (must match editor/NLS in profile):
_ISY_TEMP_F_UOM = 17 # UOM for temperatures
_ISY_THERMO_MODE_UOM = 67 # UOM for thermostat mode
_ISY_THERMO_HCS_UOM = 66 # UOM for thermostat heat/cool state

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
        
        # Get nodejs pool controller api url and set up data
        try:
            if 'api_url' in self.polyConfig['customParams']:
                self.apiBaseUrl = self.polyConfig['customParams']['api_url']
                
                # Get all data from nodejs pool controller api
                allData = requests.get(url='{}/all'.format(self.apiBaseUrl))
                self.allDataJson = allData.json()
                
                if 'circuits_not_used' in self.polyConfig['customParams']:
                    
                    # Get the list of circuits that are not in use
                    self.circuitsNotUsed = eval('[' + self.polyConfig['customParams']['circuits_not_used'] + ']')

                    # Get circuits in use
                    allCircuits = self.allDataJson['circuit']
                    circuitsUsed = copy.deepcopy(allCircuits)
                    circuitsNotUsed = self.circuitsNotUsed
                    for key in allCircuits.keys():
                        for circuitNotUsed in circuitsNotUsed:
                            if key == circuitNotUsed:
                                del circuitsUsed[key]
                                
                    self.circuits = circuitsUsed
                
                else:
                    self.circuits = self.allDataJson['circuit']
                    
                # Get temperature data
                temperatureData = requests.get(url='{}/temperatures'.format(self.apiBaseUrl))
                self.temperatureDataJson = temperatureData.json()
                
            else:
                LOGGER.error('NodeJs Pool Controller API url required in order to establish connection.  Enter custom parameter of \'api_url\' in Polyglot configuration.')
                return False
        except Exception as ex:
            LOGGER.error('Error reading NodeJs Pool Controller API url from Polyglot Configuration: %s', str(ex))
            return False
        
        self.discover()
        
    def shortPoll(self):
        for node in self.nodes:
            self.nodes[node].update()
    
    def discover(self, command = None):
        
        # Discover pool circuit nodes
        LOGGER.info('Found {} Circuits'.format(len(self.circuits)))
        
        if self.circuits:
        
            for circuit in sorted(self.circuits, key=int):
                id = circuit
                number = circuit
                address = self.circuits[circuit].get('numberStr')
                name = self.circuits[circuit].get('friendlyName').title()
                status = self.circuits[circuit].get('status')
                
                if address not in self.nodes:
                    self.addNode(Circuit(self, self.address, id, address, name, status, number, self.apiBaseUrl))
                else:
                    LOGGER.info('Circuit {} already configured.'.format(name))
            
            # Add pool and spa temperature nodes
            temperatures = ['spa','pool']
                  
            for temperature in temperatures:
                id = temperature
                address = ('{}_heat'.format(temperature))
                name = ('{} Heat'.format(temperature)).title()
                type = temperature
                
                if address not in self.nodes:
                    self.addNode(Temperature(self, self.address, id, address, name, type, self.temperatureDataJson, self.apiBaseUrl))
                else:
                    LOGGER.info('Temperature {} already configured.'.format(name))
    
    def update(self, report=True):
        
        if self.apiBaseUrl:
            
            # Get node js pool controller status
            controllerData = requests.get(url='{}/all'.format(self.apiBaseUrl))
            if controllerData.status_code == 200:
                self.setDriver('ST', 1, report)
            else:
                self.setDriver('ST', 0, report)  
            
            # Get temperatures
            temperatureData = requests.get(url='{}/temperatures'.format(self.apiBaseUrl))
            temperatureDataJson = temperatureData.json()['temperature']
            airTemp = temperatureDataJson['airTemp']
            poolTemp = temperatureDataJson['poolTemp']
            poolSetpoint = temperatureDataJson['poolSetPoint']
            spaTemp = temperatureDataJson['spaTemp']
            spaSetpoint = temperatureDataJson['spaSetPoint']
            poolHeatMode = temperatureDataJson['poolHeatMode']
            spaHeatMode = temperatureDataJson['spaHeatMode']
            
            self.setDriver('CLITEMP', airTemp, report)
            self.setDriver('GV2', poolTemp, report)
            self.setDriver('GV3', poolSetpoint, report)
            self.setDriver('GV5', spaTemp, report)
            self.setDriver('GV6', spaSetpoint, report)
            
            # Get specific circuit statuses
            allData = requests.get(url='{}/all'.format(self.apiBaseUrl))
            allDataJson = allData.json()
            circuits = allDataJson['circuit']                    
            for circuit in circuits:
                circuitType = circuits[circuit].get('circuitFunction')
                if circuitType == 'Pool':
                    status = circuits[circuit].get('status')
                    self.setDriver('GV1', status, report)
                    if poolHeatMode and status == 1:
                        self.setDriver('GV0', 1, report)
                if circuitType == 'Spa':
                    status = circuits[circuit].get('status')
                    self.setDriver('GV4', status, report)
                    if spaHeatMode and status == 1:
                        self.setDriver('GV0', 1, report)

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': _ISY_BOOL_UOM},
        {'driver': 'GV0', 'value': 0, 'uom': _ISY_INDEX_UOM},        
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
    
    def __init__(self, controller, primary, id, address, name, status, number, apiBaseUrl):
        super(Circuit, self).__init__(controller, primary, address, name)
        self.name = name
        self.status = status
        self.number = number
        self.apiBaseUrl = apiBaseUrl

    def start(self):
        self.query()
        LOGGER.info('{} ready!'.format(self.name))
    
    def update(self):
        self.get_status()
            
    def query(self, command=None):
        self.update()
        self.reportDrivers()
        
    def get_status(self, report=True):
        circuitData = requests.get(url='{0}/circuit/{1}'.format(self.apiBaseUrl, self.number))
        circuitDataJson = circuitData.json()
        status = circuitDataJson['status']
        self.setDriver('ST', status, report)
        
    def cmd_don(self, command):
        requests.get(url='{0}/circuit/{1}/toggle'.format(self.apiBaseUrl, self.number))
        self.update()
        print (self.name + ' turned on')

    def cmd_dof(self, command):
        requests.get(url='{0}/circuit/{1}/toggle'.format(self.apiBaseUrl, self.number))
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
    
    def __init__(self, controller, primary, id, address, name, type, temperatureDataJson, apiBaseUrl):
        super(Temperature, self).__init__(controller, primary, address, name)
        self.name = name
        self.type = type
        self.temperatureDataJson = temperatureDataJson
        self.apiBaseUrl = apiBaseUrl
        
    def update(self):
        self.get_status()
        
    def query(self, command=None):
        self.update()
        self.reportDrivers()
        
    def get_status(self, report=True):
        temperatureData = requests.get(url='{}/temperatures'.format(self.apiBaseUrl))
        temperatureDataJson = temperatureData.json()['temperature']
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
        temperatureData = requests.get(url='{}/temperatures'.format(self.apiBaseUrl))
        temperatureDataJson = temperatureData.json()['temperature']
        if self.type == 'spa':
            status = temperatureDataJson['spaHeatMode']
            if status == 0:
                requests.get(url='{}/spaheat/mode/1'.format(self.apiBaseUrl))  
        else:
            status = temperatureDataJson['poolHeatMode']
            if status == 0:
                requests.get(url='{}/poolheat/mode/1'.format(self.apiBaseUrl))

    def cmd_dof(self, command):
        temperatureData = requests.get(url='{}/temperatures'.format(self.apiBaseUrl))
        temperatureDataJson = temperatureData.json()['temperature']
        if self.type == 'spa':
            status = temperatureDataJson['spaHeatMode']
            if status == 1:
                requests.get(url='{}/spaheat/mode/0'.format(self.apiBaseUrl))       
        else:
            status = temperatureDataJson['poolHeatMode']
            if status == 1:
                requests.get(url='{}/poolheat/mode/0'.format(self.apiBaseUrl))

    def cmd_set_temp(self, command):        
        value = int(command.get('value'))
        if self.type == 'spa':
            requests.get(url='{0}/spaheat/setpoint/{1}'.format(self.apiBaseUrl, value))
            self.update()
        else:
            requests.get(url='{0}/poolheat/setpoint/{1}'.format(self.apiBaseUrl, value))
            self.update()
        
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': _ISY_INDEX_UOM},
        {'driver': 'CLISPH', 'value': 0, 'uom': _ISY_TEMP_F_UOM},
        {'driver': 'CLITEMP', 'value': 0, 'uom': _ISY_TEMP_F_UOM},
        {'driver': 'CLIMD', 'value': 0, 'uom': _ISY_THERMO_MODE_UOM},
        {'driver': 'CLIHCS', 'value': 0, 'uom': _ISY_THERMO_HCS_UOM},
        {'driver': 'CLISPC', 'value': 0, 'uom': _ISY_TEMP_F_UOM}
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
