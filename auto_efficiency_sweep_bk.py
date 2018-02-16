import sys
import numpy as np
import os
import time
import visa
import signal
import datetime
import csv


import matplotlib.pyplot as plt

os.system('clear')
args = sys.argv

# Change Settling time here !! -----------------
settle_time = 1.0
# ----------------------------------------------


# Set to 1 if using BK precision 9132B !! -----------------
BK_PSU = 0


def print_equipment_id():

    print(psu.query('*IDN?'))
    print(load.query('*IDN?')+'\n')


def change_setpoints(volts, current):

    psu.write('volt {}'.format(volts))
    load.write('curr:stat:l1 {}'.format(current))


def read_input_data():

    return psu.query_ascii_values('meas:volt?')[0], psu.query_ascii_values('meas:curr?')[0]


def read_output_data():

    return load.query_ascii_values('meas:volt?')[0], load.query_ascii_values('meas:curr?')[0]


def turn_supply_off():

    psu.write('output off')


def init_supply():

    if not BK_PSU:
        # KeySight PSU
        psu.write('curr {}'.format(current_limit))
        psu.write('volt 0')
        psu.write('output on')

    else:

        # BK PSU
        psu.write('syst:rem')
        psu.write('outp:par')
        psu.write('volt 0')
        psu.write('curr {}'.format(current_limit))
        psu.write('output on')

    time.sleep(2)


def signal_handler(signal, frame):

    load.write('abort')
    psu.write('output off')

    print('Aborting...')
    sys.exit()


print(
    '''
    ======            AUTO EFFICIENCY TEST                 =======

    400W MAX (Single load module) - USING CHROMA + Keysight (OR BK)
    Settling time = {}s
    Set VISA Resource Names to:  ( ChromaLoad   &  PSU ) in NIMAX
    Parameters = Vin(min) Vin(nom) Vin(max) Load(min) Load(max) #Points IinOffset IoutOffset current_limit'''.format(settle_time))

print('\n')

# Configure cntrl + c abort event
signal.signal(signal.SIGINT, signal_handler)

volt_setpoint = [float(i) for i in args[1:4]]
current_range = [float(i) for i in args[4:7]]
iin_offset = float(args[7])
iout_offset = float(args[8])
current_limit = float(args[9])


x0, xn, points = current_range
load_currents = np.linspace(x0, xn, points)

# Open VISA Resources - Change Names Here ! ! ! -----------------------------------

rm = visa.ResourceManager()
if not BK_PSU:
    psu = rm.open_resource('PSU')           #  < ----------------  Keysight Power Supply
else:
    psu = rm.open_resource('PSU_bk')        #  < ----------------  BK Power Supply


load = rm.open_resource('chroma_load2')   #  < ----------------  eLoad

# ---------------------------------------------------------------------------------
print_equipment_id()


print('The max voltage to be tested is {:.2f}V and a max load current of {:.2f}A'.format(max(volt_setpoint),max(load_currents)))
print('The source current limit is set to {:2.2f}A'.format(current_limit))
print('The input current offset is set to {:2.2f}mA'.format(iin_offset/1e-3))
print('The output current offset is set to {:2.2f}mA\n'.format(iout_offset/1e-3))
menu = raw_input('Do you want to continue? (Y/N)')

if menu != 'Y':
    print('Exiting...')
    load.write('abort')
    turn_supply_off()
    psu.close()
    load.close()
    sys.exit()

print('Starting... to Abort press Ctrl + c at any time\n')

print('Turning Supply ON')


# Initialize PSU

init_supply()
time.sleep(2)


# Configure E-Load for CCH
print('Configuring Load CH7')
load.write('chan 7')
load.write('mode cch')
load.write('curr:stat:l1 0')
load.write('load on')


data_0 = []
data_1 = []
data_2 = []


for voltage in volt_setpoint:

    for current in load_currents:

        change_setpoints(voltage,current)
        time.sleep(settle_time)

        vin, iin = read_input_data()
        iin += iin_offset
        pin = vin * iin
        vout, iout = read_output_data()
        iout += iout_offset
        pout = vout * iout
        eff = pout/(pin+0.00000001)*100

        if voltage == volt_setpoint[0]:
            data_0.append([vin, iin, pin, vout, iout, pout, eff])
        if voltage == volt_setpoint[1]:
            data_1.append([vin, iin, pin, vout, iout, pout, eff])
        if voltage == volt_setpoint[2]:
            data_2.append([vin, iin, pin, vout, iout, pout, eff])

        print('|\t{:.2f}V\t{:.2f}A\t{:.2f}W\t{:.2f}V\t{:.2f}A\t{:.2f}W\t{:.2f}%' \
              .format(vin, iin, pin, vout, iout, pout, eff))

data_min = np.array(data_0)
data_typ = np.array(data_1)
data_max = np.array(data_2)

print('Turning Load OFF\n')

turn_supply_off()
load.write('load off')


print('Saving Data...')


time_stamp = time.time()
time_str = datetime.datetime.fromtimestamp(time_stamp).strftime('%Y_%m_%d_%H_%M_%S')

with open('efficiency_test_'+time_str+'.csv', 'wb') as f:
    wtr = csv.writer(f, delimiter= ',')

    wtr.writerows([['Vin', 'Iin', 'Pin', 'Vout', 'Iout', 'Pout', 'Eff']])
    wtr.writerows(data_min)
    wtr.writerows('\n')
    wtr.writerows(data_typ)
    wtr.writerows('\n')
    wtr.writerows(data_max)

plt.figure(1)
plt.plot(data_min[:, 4], data_min[:, 6], \
         label='Vin={:.2f}V'.format(volt_setpoint[0]), linewidth='2')
plt.plot(data_typ[:, 4], data_typ[:, 6], \
         label='Vin={:.2f}V'.format(volt_setpoint[1]), linewidth='2')
plt.plot(data_max[:, 4], data_max[:, 6], \
         label='Vin={:.2f}V'.format(volt_setpoint[2]), linewidth='2')

plt.title('Efficiency vs Load')
plt.xlabel('Load [A]')
plt.ylabel('Efficiency [%]')
plt.ylim((40.0, 100.0))
plt.grid()
plt.legend(loc='lower right')

#plt.axes([current_range[0], current_range[1], 50, 110])


plt.figure(2)
plt.plot(data_min[:, 4], data_min[:, 3], \
         label='Vin={:.2f}V'.format(volt_setpoint[0]), linewidth='2')
plt.plot(data_typ[:, 4], data_typ[:, 3], \
         label='Vin={:.2f}V'.format(volt_setpoint[1]), linewidth='2')
plt.plot(data_max[:, 4], data_max[:, 3], \
         label='Vin={:.2f}V'.format(volt_setpoint[2]), linewidth='2')

plt.title('Vout vs Load')
plt.xlabel('Load [A]')
plt.ylabel('Vout [V]')
plt.grid()
plt.legend()

plt.show()
