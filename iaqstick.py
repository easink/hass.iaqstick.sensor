"""
Support for iAQ-Stick CO2 sensor.

Initial code stolen from Robert Budde (robert@projekt131.de).

Copyright 2013 Robert Budde                       robert@projekt131.de
Copyright 2017 Andreas Rydbrink             github.com/easink/iaqstick

This plugin is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This plugin is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this plugin. If not, see <http://www.gnu.org/licenses/>.

# /etc/udev/rules.d/99-iaqstick.rules
# SUBSYSTEM=="usb", ATTR{idVendor}=="03eb", ATTR{idProduct}=="2013", MODE="666"
# udevadm trigger
"""


APPLIEDSENSOR = 0x03eb
IAQ_STICK     = 0x2013

import logging
import usb.core
import usb.util
from time import sleep

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA

# REQUIREMENTS = ['pyusb']

_LOGGER = logging.getLogger(__name__)

# CONF_SERIAL_DEVICE = 'serial_device'

DEFAULT_NAME = 'iAQ-Stick CO2 Sensor'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    # vol.Required(CONF_SERIAL_DEVICE): cv.string,
})


#    global SUBSCRIPTION_REGISTRY
#    SUBSCRIPTION_REGISTRY = pywemo.SubscriptionRegistry()
#    SUBSCRIPTION_REGISTRY.start()
#
#    def stop_wemo(event):
#        """Shutdown Wemo subscriptions and subscription thread on exit."""
#        _LOGGER.info("Shutting down subscriptions.")
#        SUBSCRIPTION_REGISTRY.stop()
#
#    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_wemo)

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the available CO2 sensors."""

    dev = iAQ_Stick(config.get(CONF_NAME))
    if dev.setup() is True:
        add_devices([dev])


class iAQ_Stick(Entity):
    """Representation of an CO2 sensor."""

    def __init__(self, name, verbose=True):
        """Initialize a new PM sensor."""
        self._name = name
        self._state = 0
        self._verbose = verbose
        # self._serial = serial_device
        self._info_tags = {}
        self._def = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return "ppm"

    def _xfer_type1(self, msg):
        out_data = bytes('@{:04X}{}\n@@@@@@@@@@'.format(self._type1_seq, msg), 'utf-8')
        self._type1_seq = (self._type1_seq + 1) & 0xFFFF
        ret = self._dev.write(0x02, out_data[:16], 1000)
        # ret = self._dev.write(0x02, out_data[:16], self._intf, 1000)
        in_data = bytes()
        while True:
            ret = bytes(self._dev.read(0x81, 0x10, 1000))
            # ret = bytes(self._dev.read(0x81, 0x10, self._intf, 1000))
            if len(ret) == 0:
                break
            in_data += ret
        return in_data.decode('iso-8859-1')

    def _xfer_type2(self, msg):
        out_data = bytes('@', 'utf-8') + self._type2_seq.to_bytes(1, byteorder='big') + bytes('{}\n@@@@@@@@@@@@@'.format(msg), 'utf-8')
        self._type2_seq = (self._type2_seq + 1) if (self._type2_seq < 0xFF) else 0x67
        ret = self._dev.write(0x02, out_data[:16], 1000)
        # ret = self._dev.write(0x02, out_data[:16], self._intf, 1000)
        in_data = bytes()
        while True:
            ret = bytes(self._dev.read(0x81, 0x10, 1000))
            # ret = bytes(self._dev.read(0x81, 0x10, self._intf, 1000))
            if len(ret) == 0:
                break
            in_data += ret
        return in_data

    def setup(self):
        self._dev = usb.core.find(idVendor=APPLIEDSENSOR, idProduct=IAQ_STICK)
        if self._dev is None:
            _LOGGER.error('iaqstick: iAQ Stick not found')
            return
        self._intf = 0
        self._type1_seq = 0x0001
        self._type2_seq = 0x67

        try:
            if self._dev.is_kernel_driver_active(self._intf):
                self._dev.detach_kernel_driver(self._intf)

            self._dev.set_configuration(0x01)
            usb.util.claim_interface(self._dev, self._intf)
            self._dev.set_interface_altsetting(self._intf, 0x00)

            manufacturer = usb.util.get_string(self._dev, 0x101, 0x409).encode('ascii')
            # manufacturer = usb.util.get_string(self._dev, 0x101, 0x409).encode('ascii')
            # manufacturer = usb.util.get_string(self._dev, 0x101, 0x01, 0x409)
            product = usb.util.get_string(self._dev, 0x101, 0x409).encode('ascii')
            # product = usb.util.get_string(self._dev, 0x101, 0x02, 0x409)
            _LOGGER.info('iaqstick: Manufacturer: {} - Product: {}'.format(manufacturer, product))
            ret = self._xfer_type1('*IDN?')
            if self._verbose:
                print(ret)
            self._dev.write(0x02, bytes('@@@@@@@@@@@@@@@@', 'utf-8'), 1000)
            # self._dev.write(0x02, bytes('@@@@@@@@@@@@@@@@', 'utf-8'), self._intf, 1000)
            ret = self._xfer_type1('KNOBPRE?')
            if self._verbose:
                print(ret)
            ret = self._xfer_type1('WFMPRE?')
            if self._verbose:
                print(ret)
            ret = self._xfer_type1('FLAGS?')
            if self._verbose:
                print(ret)
        except Exception as e:
            _LOGGER.error("iaqstick: init interface failed - {}".format(e))
            return False

        # self._sh.scheduler.add('iAQ_Stick', self._update_values, prio = 5, cycle = self._update_cycle)
        _LOGGER.info("iaqstick: init successful")
        return True

    def stop(self):
        try:
            usb.util.release_interface(self._dev, self._intf)
        except Exception as e:
            _LOGGER.error("iaqstick: releasing interface failed - {}".format(e))
        try:
            # self._sh.scheduler.remove('iAQ_Stick')
            pass
        except Exception as e:
            _LOGGER.error("iaqstick: removing iAQ_Stick from scheduler failed - {}".format(e))

    def update(self):
        #_LOGGER.debug("iaqstick: update")
        try:
            self._xfer_type1('FLAGGET?')
            meas = self._xfer_type2('*TR')
            ppm = int.from_bytes(meas[2:4], byteorder='little')
            _LOGGER.debug('iaqstick: ppm: {}'.format(ppm))
            #_LOGGER.debug('iaqstick: debug?: {}'.format(int.from_bytes(meas[4:6], byteorder='little')))
            #_LOGGER.debug('iaqstick: PWM: {}'.format(int.from_bytes(meas[6:7], byteorder='little')))
            #_LOGGER.debug('iaqstick: Rh: {}'.format(int.from_bytes(meas[7:8], byteorder='little')*0.01))
            #_LOGGER.debug('iaqstick: Rs: {}'.format(int.from_bytes(meas[8:12], byteorder='little')))
            # if 'ppm' in self._info_tags:
            #     for item in self._info_tags['ppm']['items']:
            #         item(ppm, 'iAQ_Stick', 'USB')
            if (ppm >= 0) & (ppm <= 5000):
                self._state = ppm
        except Exception as e:
            _LOGGER.error("iaqstick: update failed - {}".format(e))

    # def _parse_item(self, item):
    #     if 'iaqstick_info' in item.conf:
    #         _LOGGER.debug("parse item: {0}".format(item))
    #         info_tag = item.conf['iaqstick_info'].lower()
    #         if not info_tag in self._info_tags:
    #             self._info_tags[info_tag] = {'items': [item], 'logics': []}
    #         else:
    #             self._info_tags[info_tag]['items'].append(item)
    #     return None

    # def update(self):
    #     """Read from sensor and update the state."""
    #     from pmsensor import co2sensor

    #     _LOGGER.debug("Reading data from CO2 sensor")
    #     try:
    #         ppm = co2sensor.read_mh_z19(self._serial)
    #         # values from sensor can only between 0 and 5000
    #         if (ppm >= 0) & (ppm <= 5000):
    #             self._state = ppm
    #     except OSError as err:
    #         _LOGGER.error("Could not open serial connection to %s (%s)",
    #                       self._serial, err)
    #         return

    def should_poll(self):
        """Sensor needs polling."""
        return True

# logging.basicConfig(level=logging.DEBUG)

#Application Version: 2.19.0 (Id: Form1.frm 1053 2010-06-30 11:00:09Z patrik.arven@appliedsensor.com )
#
#Device 0:
#Name: iAQ Stick
#Firmware: 1.12p5 $Revision: 346 $
#Protocol: 5
#Hardware: C
#Processor: ATmega32U4
#Serial number: S/N:48303230303415041020
#Web address:
#Plot title: Air Quality Trend
#
#Channels: 5
#... Channel 0:CO2/VOC level
#... Channel 1:Debug
#... Channel 2:PWM
#... Channel 3:Rh
#... Channel 4:Rs
#Knobs: 8
#... Knob CO2/VOC level_warn1:1000
#... Knob CO2/VOC level_warn2:1500
#... Knob Reg_Set:151
#... Knob Reg_P:3
#... Knob Reg_I:10
#... Knob Reg_D:0
#... Knob LogInterval:0
#... Knob ui16StartupBits:1
#Flags: 5
#... WARMUP=&h0000&
#... BURN-IN=&h0000&
#... RESET BASELINE=&h0000&
#... CALIBRATE HEATER=&h0000&
#... LOGGING=&h0000&
#
#@013E;;DEBUG:
#Log:
#buffer_size=&h1400;
#address_base=&h4800;
#readindex=&h0040;
#Write index=&h0000;
#nValues=&h0000;
#Records=&h0000;
#nValues (last)=&h0000;
#uint16_t g_u16_loop_cnt_100ms=&h08D4;
#;\x0A

#https://github.com/mknx/smarthome/blob/master/plugins/iaqstick/__init__.py
