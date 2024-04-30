#!/usr/bin/env python3
import json
import os
import sys
import time
import shutil

# Constants and Globals
DEBUG = False

def debug_print(message: str, *args):
    """Prints a message if debugging is enabled."""
    if DEBUG:
        print(message, *args)

def small_number_check(number: float) -> float:
    """Converts extremely small floating-point numbers to zero."""
    return 0.0 if 'e' in str(number) else number

# Function to parse data lines
def parse_data_line(line: str, wake_iters: int):
    """Extracts numerical data from a specified line in history files after wake iterations."""
    try:
        line_data = line.split()
        line_data = [x for x in line_data if x]
        line_data.pop(0)  # Remove the first element (usually a label)
        return [small_number_check(float(x.strip())) for x in line_data]
    except ValueError as e:
        debug_print(f"Error parsing line: {e}")
        return []

def format_value(value: float, precision: int = 5) -> str:
    """Formats the value to the specified precision and ensures it has a sign and correct number of decimals."""
    formatted_value = f"{value:.{precision}f}"
    if not formatted_value.startswith('-'):
        formatted_value = ' ' + formatted_value
    return formatted_value

def append_beta_data(output_file, datapoint, run, pos, output_data, db):
    """Appends beta data and creates corresponding XML table entries."""
    for beta in output_data[datapoint][run][pos]:
        output_file.write(f'      <tableData breakPoint="{float(beta):.1f}">\n')
        mach_aoa_data = output_data[datapoint][run][pos][beta]
        for mach in sorted(mach_aoa_data):
            output_file.write(f'        {float(mach):.3f}  ')
            for aoa in sorted(mach_aoa_data[mach]):
                value = format_value(mach_aoa_data[mach][aoa])
                output_file.write(f'{value}  ')
            output_file.write('\n')
        output_file.write('      </tableData>\n\n')

def process_data_points(output_file, output_data, db):
    """Processes each data point to generate XML structures."""
    for datapoint in output_data:
        print('#####', datapoint)
        output_file.write(f'  <!-- {datapoint.upper()} -->\n')
        for run in output_data[datapoint]:
            print('-', run)
            output_file.write(f'  <!-- {run} -->\n')
            for pos in output_data[datapoint][run]:
                betas = sorted(set(float(d['beta']) for d in db[run][pos]))

                # Generate or update entries in the output data structure
                for d in db[run][pos]:
                    beta = format_value(float(d['beta']), 1)
                    mach = format_value(float(d['Mach']), 3)
                    aoa = format_value(float(d['AoA']), 3)
                    value = small_number_check(float(f"{d[datapoint]:.5f}"))

                    if run != 'base':
                        base_value = small_number_check(float(output_data[datapoint]['base'][0][beta][mach][aoa]))
                        value -= base_value

                    output_data[datapoint][run][pos].setdefault(beta, {}).setdefault(mach, {})[aoa] = format_value(value)

                # Write to JSON after updating data
                with open('./outputData.json', 'w+') as jf:
                    json.dump(output_data, jf, sort_keys=True, indent=4)

                # Handle XML generation for this data point
                if run == 'ground_effect':
                    continue

                func_name = f'aero/{datapoint}_{run}_{pos}' if run != 'base' else f'aero/{datapoint}_{run}'
                output_file.write(f'  <function name="{func_name}">\n')
                output_file.write('    <table>\n')
                output_file.write('      <independentVar lookup="row">velocities/mach</independentVar>\n')
                output_file.write('      <independentVar lookup="column">aero/alpha-deg</independentVar>\n')
                output_file.write('      <independentVar lookup="table">aero/beta-deg</independentVar>\n')
                append_beta_data(output_file, datapoint, run, pos, output_data, db)
                output_file.write('    </table>\n')
                output_file.write('  </function>\n\n')

                # Handling interpolation for non-base and non-ground effect data
                if run not in ['base', 'ground_effect']:
                    interpolate_data_points(output_file, datapoint, run, output_data)

def interpolate_data_points(output_file, datapoint, run, output_data):
    """Creates interpolation functions for aerodynamic data points."""
    output_file.write(f'  <function name="aero/{datapoint}_{run}">\n')
    output_file.write('    <interpolate1d>\n')
    property_path = 'position/h-agl-m' if run == 'ground_effect' else f'fcs/surfaces/{run}-pos-deg'
    output_file.write(f'      <property>{property_path}</property>\n')
    
    # Sorting and interpolating data based on position
    positions = sorted(output_data[datapoint][run])
    last_position = None
    for position in positions:
        if last_position is None or last_position < 0 and position > 0:
            output_file.write('      <value>0</value> <value>0</value>\n')
        output_file.write(f'      <value>{position}</value> <property>aero/{datapoint}_{run}_{position}</property>\n')
        last_position = position

    if last_position < 0:
        output_file.write('      <value>0</value> <value>0</value>\n')
    output_file.write('    </interpolate1d>\n')
    output_file.write('  </function>\n\n')

def initialize_output_data_structure():
    """Initialize and return the output data structure based on your specific needs."""
    output_data = {
        'CL': {}, 'CDtot': {}, 'CS': {}, 'CMx': {}, 'CMy': {}, 'CMz': {}
        # Initialize further as needed
    }
    return output_data

def load_database():
    """Load or generate the database from parsed VSP data."""
    db = {}
    # Load your database here, potentially from a JSON file or through computation
    return db



# Read parameters from a configuration file
with open('./runparams.json', 'r') as param_file:
    params = json.load(param_file)

# Prepare output files
output_json_path = './output/outputData.json'
output_data_file = open(output_json_path, 'w+')
output_file = open(params['output_file'], 'w+')

# Open the stability file and base history file
stab_file_path = os.path.join(params['stab_file'], params['vspname'] + '.stab')
stab_file = open(stab_file_path, 'r')
input_base = params['base_file']
input_base_path = os.path.join(input_base, params['vspname'] + '.history')
input_txt_base = open(input_base_path, 'r').readlines()
input_txt = {}

# Default number of wake iterations
wake_iterations = 3

# Process command line arguments
for arg in sys.argv:
    if '--debug' in arg:
        DEBUG = True
    if arg.startswith('-w'):
        wake_iterations = int(arg[2:])

# Parse the history files for each run configuration
input_txt = {}
for f, configs in params['files'].items():
    input_txt[f] = {os.path.basename(c): open(os.path.join(c, params['vspname'] + '.history')).readlines() for c in configs}

# Database for storing parsed data
db = {'base': {0: []}}
data_order = ['Mach', 'AoA', 'beta', 'CL', 'CDo', 'CDi', 'CDtot', 'CS', 'L/D', 'E', 'CFx', 'CFz', 'CFy', 'CMx', 'CMy', 'CMz', 'T/QS']


# Process the base file data
print(f"Processing base data from {input_base_path}")
for i, line in enumerate(input_txt_base):
    if line.startswith('Solver Case:'):
        data_line = input_txt_base[i + 2 + wake_iterations]
        parsed_data = parse_data_line(data_line, wake_iterations)
        dataset = dict(zip(data_order, parsed_data))
        db['base'][0].append(dataset)

# Process data for each configuration
for s, files in input_txt.items():
    db[s] = {}
    for p, lines in files.items():
        db[s][p] = []
        for i, line in enumerate(lines):
            if line.startswith('Solver Case:'):
                data_line = lines[i + 2 + wake_iterations]
                parsed_data = parse_data_line(data_line, wake_iterations)
                dataset = dict(zip(data_order, parsed_data))
                db[s][p].append(dataset)

# Save parsed data to a JSON file
with open('./output/dataset.json', 'w+') as jf:
    json.dump(db, jf, sort_keys=True, indent=4)

# The following part of the script generates JSBSim configuration files.
# It constructs XML entries for each datapoint across various runs and positions.
# The script handles formatting, adjustment of small numbers, and XML structuring.


desc = '''Generated by vsp2jsbsim.py
Author: Jüttner Domokos\n
Based on the work of Richard Harrison'''
output_file.write('<!--\n')
output_file.write(desc)
output_file.write('-->\n')
output_file.write('<aerodynamics>\n\n')
output_file.write('  <function name="aero/beta-deg-abs">\n')
output_file.write('    <description>Beta absolute value</description>\n')
output_file.write('    <abs>\n')
output_file.write('      <property>aero/beta-deg</property>\n')
output_file.write('    </abs>\n')
output_file.write('  </function>\n')
output_file.write('\n')
output_file.write('  <function name="aero/pb">\n')
output_file.write('    <description>PB Denormalization</description>\n')
output_file.write('    <product>\n')
output_file.write('      <property>aero/bi2vel</property>\n')
output_file.write('      <property>velocities/p-aero-rad_sec</property>\n')
output_file.write('    </product>\n')
output_file.write('  </function>\n')
output_file.write('\n')
output_file.write('  <function name="aero/qb">\n')
output_file.write('    <description>For denormalization</description>\n')
output_file.write('    <product>\n')
output_file.write('      <property>aero/ci2vel</property>\n')
output_file.write('      <property>velocities/q-aero-rad_sec</property>\n')
output_file.write('    </product>\n')
output_file.write('  </function>\n')
output_file.write('\n')
output_file.write('  <function name="aero/rb">\n')
output_file.write('    <description>For denormalization</description>\n')
output_file.write('    <product>\n')
output_file.write('      <property>aero/bi2vel</property>\n')
output_file.write('      <property>velocities/r-aero-rad_sec</property>\n')
output_file.write('    </product>\n')
output_file.write('\n')
output_file.write('  </function>\n')

# Initialize the output data structure (if not done elsewhere in your code)
output_data = initialize_output_data_structure()

# Load your database of parsed VSP data (if not loaded elsewhere)
db = load_database()

# Process the data points
process_data_points(output_file, output_data, db)


# for d in outputData.keys():
#     ge = outputData[d]['ground_effect']
#     alts = [i for i in ge.keys()]
#     betas = [i for i in ge[alts[0]].keys()]             
#     machs = [i for i in ge[betas[0]][alts[0]].keys()]
#     aoa = [i for i in ge[betas[0]][alts[0]][machs[0]].keys()]
#     output_file.write('  <function name="aero/' + datapoint + '_' + run + '_' + str(pos) + '">\n')
#     output_file.write('    <table>\n')
#     output_file.write('      <independentVar lookup="row">velocities/mach</independentVar>\n')
#     output_file.write('      <independentVar lookup="column">aero/alpha-deg</independentVar>\n')
#     output_file.write('      <independentVar lookup="table">position/h-agl-m</independentVar>\n')
#     for m in machs:
#         output_file.write('      <tableData breakPoint="' + str(float(agl)) + '">\n')
#         txt_CL = '                '
#         for a in aoa:
#             txt_CL += str(a) + ' '
#         txt_CL += '\n'
#         for a in alts:
#             line = ' ' * 6 + a + ' '
#             for c in 
            
        
#         machs = []
#         aoa = []
#         for m in outputData[datapoint][run][pos][b].keys():
#             if m not in machs:
#                 machs.append(m)
#                 for a in outputData[datapoint][run][pos][b][m].keys():
#                     a = str(float(a))
#                     if len(a.split('.')[0]) < 3:
#                         a = ' ' * (3 - len(a.split('.')[0])) + a
#                     if len(a) < 6:
#                         a += ' ' * (6 - len(a))
#                     if a not in aoa:
#                         txt_CL += a[:-3] + '    '
#                         aoa.append(a)
#         txt_CL = txt_CL[:-1] + '\n'

#         for m in outputData[datapoint][run][pos][b].keys():
#             line = '        ' + str(float(m)) + '  '
#             for c in outputData[datapoint][run][pos][b][m].values():
#                 line += str(c) + '  '
#             txt_CL += line[:-2] + '\n'

#         output_file.write(txt_CL[:-1] + '\n')
#         output_file.write('      </tableData>\n\n')
#     output_file.write('    </table>\n')
#     output_file.write('  </function>\n\n')

# Stability - pretty much copypaste of pinto's stab_format.py
print('##### stability')
data = []

mach = -9999
alpha = -9999
beta = -9999
cmlp = -9999
cmlr = -9999
cmma = -9999
cmmb = -9999
cmmq = -9999
cmnb = -9999
cmnr = -9999
cmnp = -9999
cfyp = -9999
cfyr = -9999

line = stab_file.readline()

def getdata(line):
    while '  ' in line:
        line = line.replace('  ', ' ')
    return line.split(' ')

while line != "":
    # print(line)
    line_arr = getdata(line)
    # gather main info
    if line[0:5] == "Mach_":
        mach = float(line[21:33])
    elif line[0:4] == "AoA_":
        alpha = float(line[21:33])
    elif line[0:5] == "Beta_":
        beta = float(line[21:33])

    # gather coefficient info
    elif line[0:3] == "CMx":
        cmlp = float(line_arr[4])  # wrt p per rad colum
        cmlr = float(line_arr[6])  # wrt r per rad column
    elif line[0:3] == "CMy":
        cmma = float(line_arr[2])
        cmmb = float(line_arr[3])
        cmmq = float(line_arr[5])
    elif line[0:3] == "CMz":
        cmnb = float(line_arr[3])
        cmnr = float(line_arr[4])
        cmnp = float(line_arr[6])
    elif line[0:2] == "CS":
        cfyp = float(line_arr[4])
        cfyr = float(line_arr[6])

    # output data

    elif line[0:8] == "# Result":
        data.append({'mach' : mach,
                     'alpha' : alpha,
                     'beta' : beta,
                     'cmlp' : cmlp,
                     'cmlr' : cmlr,
                     'cmma' : cmma,
                     'cmmb' : cmmb,
                     'cmmq' : cmmq,
                     'cmnb' : cmnb,
                     'cmnr' : cmnr,
                     'cmnp' : cmnp,
                     'cfyp' : cfyp,
                     'cfyr' : cfyr,
                     })

        # reinit values
        mach = -9999
        alpha = -9999
        beta = -9999
        cmlp = -9999
        cmlr = -9999
        cmma = -9999
        cmmb = -9999
        cmmq = -9999
        cmnb = -9999
        cmnr = -9999
        cmnp = -9999
        cfyp = -9999
        cfyr = -9999

    line = stab_file.readline()

stab_file.close()

# build an array of mach, alpha, and beta values
mach_arr = []
alpha_arr = []
beta_arr = []

false = 0
true = 1

for i in data:
    match = false

    for j in mach_arr:
        if j == i['mach']:
            match = true
    if not match:
        mach_arr.append(i['mach'])
    match = false

    for j in alpha_arr:
        if j == i['alpha']:
            match = true
    if not match:
        alpha_arr.append(i['alpha'])
    match = false

    for j in beta_arr:
        if j == i['beta']:
            match = true
            break
    if not match:
        beta_arr.append(i['beta'])
    match = false

output_coeffs = {
    # not included are: cmmb, cmnb
    'cmlp': ['Roll damping derivative', 'aero/pb'],
    'cmlr': ['Roll moment due to yaw rate', 'aero/rb'],
    'cmmq': ['Pitch damping derivative', 'aero/qb'],
    'cmma': ['Pitch moment alpha dot', 'aero/alphadot-rad_sec'],
    'cmnp': ['Yaw moment due to roll rate', 'aero/pb'],
    'cmnr': ['Yaw damping derivative', 'aero/rb'],
    'cfyp': ['Side force due to roll rate', 'aero/pb'],
    'cfyr': ['Side force due to yaw rate', 'aero/rb'],
}

# output_file.write('<?xml version="1.0"?>\n\n')

for coeff in output_coeffs:
    debug_print(coeff)
    output_file.write('  <function name="aero/s/' + coeff + '">\n')
    output_file.write('    <description>' + output_coeffs[coeff][0] + '</description>\n')
    output_file.write('    <product>\n')
    output_file.write('      <property>' + output_coeffs[coeff][1] + '</property>\n')
    output_file.write('      <table>\n')
    output_file.write('        <independentVar lookup="row">velocities/mach</independentVar>\n')
    output_file.write('        <independentVar lookup="column">aero/alpha-deg</independentVar>\n')
    output_file.write('        <independentVar lookup="table">aero/beta-deg</independentVar>\n')
    if coeff not in params['alpha_only'] or true:
        output_file.write('        <tableData breakPoint="' + str(data[0]['beta']) + '">\n')
        output_file.write('                   ')
        for a in alpha_arr:
            a = str(a)
            if len(a.split('.')[0]) < 3:
                a = ' ' * (3 - len(a.split('.')[0])) + a
            output_file.write(str(a) + '       ')
        output_file.write('\n')
        output_file.write('           ')
        mp = str(data[0]['mach'])
        if not mp.startswith('-'):
            mp = ' ' + mp
        if len(mp.split('.')[1]) < 4:
            mp += ' ' * (4 - len(mp.split('.')[1]))
        output_file.write(mp)

    b_beta = data[0]['beta']
    b_mach = data[0]['mach']

    for i in data:
        if coeff in params['alpha_only'] and i['beta'] != 0:
            continue
        
        if b_beta != i['beta']:
            b_beta = i['beta']
            if coeff not in params['alpha_only']:
                output_file.write('\n        </tableData>\n')
                output_file.write('        <tableData breakPoint="' +
                         str(i['beta']) + '">\n')
                output_file.write('                   ')
                for a in alpha_arr:
                    a = str(a)
                    if len(a.split('.')[0]) < 3:
                        a = ' ' * (3 - len(a.split('.')[0])) + a
                    output_file.write(str(a) + '       ')

        if b_mach != i['mach']:
            b_mach = i['mach']
            output_file.write('\n           ')
            mp = str(i['mach'])
            if not mp.startswith('-'):
                mp = ' ' + mp
            if len(mp.split('.')[1]) < 4:
                mp += ' ' * (4 - len(mp.split('.')[1]))
            output_file.write(mp)

        cf = str(small_number_check(i[coeff]))
        
        if not cf.startswith('-'):
            cf = ' ' + cf
        if len(cf.split('.')[1]) < 7:
            cf += '0' * (7 - len(cf.split('.')[1]))
        output_file.write('  ' + cf)

    output_file.write('\n        </tableData>\n')
    output_file.write('      </table>\n')
    output_file.write('    </product>\n')
    output_file.write('  </function>\n\n')

outputitems = {'forces': {'lift': 'CL', 'drag': 'CDtot', 'side': 'CS'},
               'moments': {'pitch': 'CMy', 'roll': 'CMx', 'yaw': 'CMz'}}

# AXIS definitions
# for g in outputitems.keys():
#     for o in outputitems[g].keys():
#         output_file.write('  <axis name="' + o.upper() + '">\n')
#         output_file.write('    <function name="aero/' + g + '/' + o + '">\n')
#         output_file.write('      <product>\n')
#         output_file.write('         <property>aero/qbar-psf</property>\n')
#         output_file.write('         <property>metrics/Sw-sqft</property>\n')
        
#         if g == 'moments':
#             if o == 'pitch' or o == 'roll':
#                 output_file.write('         <property>metrics/bw-ft</property>\n')
#             elif o == 'yaw':
#                 output_file.write('         <property>metrics/cbarw-ft</property>\n')
                
#         output_file.write('         <sum>\n')
#         for r in outputData[outputitems[g][o]].keys():
#             output_file.write('           <property>aero/' + outputitems[g][o] + '_' + r + '</property>\n')
#         if g == 'moments':
#             if o == 'pitch':
#                 output_file.write('           <property>aero/s/cmmq</property>\n')
#             # elif o == 'roll':
#             elif False:
#                 output_file.write('           <property>aero/s/cmlp</property>\n')
#                 output_file.write('           <property>aero/s/cmlr</property>\n')
#             elif o == 'yaw':
#                 output_file.write('           <property>aero/s/cmnp</property>\n')
#                 output_file.write('           <property>aero/s/cmnr</property>\n')
#         elif g == 'force' and o == 'side':
#             output_file.write('           <property>aero/s/cfyp</property>\n')
#             output_file.write('           <property>aero/s/cfyr</property>\n')
                
#         output_file.write('        </sum>\n')
#         output_file.write('      </product>\n')
#         output_file.write('    </function>\n')
#         output_file.write('  </axis>\n\n')

# with open(params['axis_file'], 'r') as axis:
#     for l in axis.readlines():
#         output_file.write(l)
output_file.close()
output_data_file.close()
print('process time:', time.process_time())
