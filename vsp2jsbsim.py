#!/usr/bin/env python3
import commentjson
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
        
        # Gather all AoA values to create the header row
        mach_aoa_data = output_data[datapoint][run][pos][beta]
        aoa_set = set()
        for mach in mach_aoa_data:
            aoa_set.update(mach_aoa_data[mach].keys())  # Assuming keys are strings

        sorted_aoas = sorted(aoa_set, key=float)  # Sort AoAs as floats but they are stored as strings
        
        # Write AoA headers
        output_file.write(' ' * 11)  # Proper indentation
        for aoa in sorted_aoas:
            output_file.write(f'{float(aoa):10.1f}  ')
        output_file.write('\n')
        
        # Now write the Mach and corresponding values
        for mach in sorted(mach_aoa_data.keys(), key=float):
            output_file.write(f'        {float(mach):.3f}  ')
            for aoa in sorted_aoas:  # Ensure values are written in the order of the headers
                value = mach_aoa_data[mach].get(aoa, '0.00000')  # Use aoa directly since it's a string
                # Ensure value is processed as float after formatting
                formatted_value = format_value(float(value))
                output_file.write(f'{float(formatted_value):10.5f}  ')
            output_file.write('\n')
        output_file.write('      </tableData>\n\n')



def process_data_in_database(output_file, output_data, db):
    """Processes each data point to generate XML structures."""
    for datapoint in output_data:
        print('#####', datapoint)
        output_file.write(f'  <!-- {datapoint.upper()} -->\n')
        for run in output_data[datapoint]:
            output_file.write(f'  <!-- {run} -->\n')
            for pos in output_data[datapoint][run]:
                # betas = sorted(set(float(d['beta']) for d in db[run][pos]))

                # Generate or update entries in the output data structure
                for d in db[run][pos]:
                    beta = format_value(float(d['beta']), 1)
                    mach = format_value(float(d['Mach']), 3)
                    aoa = format_value(float(d['AoA']), 3)
                    value = small_number_check(float(f"{d[datapoint]:.5f}"))

                    # TODO: put this back
                    # if run != 'base':
                    #     base_value = small_number_check(float(output_data[datapoint]['base'][0][beta][mach][aoa]))
                    #     value -= base_value
                    print(type(output_data[datapoint][run]))
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

    print('last_position:', last_position)
    if float(last_position) < 0:
        output_file.write('      <value>0</value> <value>0</value>\n')
    output_file.write('    </interpolate1d>\n')
    output_file.write('  </function>\n\n')

def load_database():
    """Load or generate the database from parsed VSP data."""
    with open('./output/dataset.json', 'r') as jf:
        db = json.load(jf)
    return db

def write_axis(output_file, group, axis, properties):
    """Writes a single axis definition using a formatted string."""
    # Define a template for the axis XML structure
    axis_template = """
  <axis name="{axis_name}">
    <function name="aero/{group}/{axis}">
      <product>
        <property>aero/qbar-psf</property>
        <property>metrics/Sw-sqft</property>
        {extra_properties}
        <sum>
{properties}
        </sum>
      </product>
    </function>
  </axis>
"""

    # Conditional string inclusion based on specific criteria
    extra_properties = ''
    if group == 'moments':
        if axis == 'pitch' or axis == 'roll':
            extra_properties = '<property>metrics/bw-ft</property>\n'
        elif axis == 'yaw':
            extra_properties = '<property>metrics/cbarw-ft</property>\n'

    # Compose the property elements from the provided properties
    property_elements = '\n'.join(f'          <property>{prop}</property>' for prop in properties)

    # Fill the template with actual data
    formatted_axis = axis_template.format(
        axis_name=axis.upper(),
        group=group,
        axis=axis,
        extra_properties=extra_properties,
        properties=property_elements
    )

    # Write the formatted string to file
    output_file.write(formatted_axis)

def assign_aerodynamics_to_axis(output_file, output_data):
    """Generates aerodynamic properties based on the specified structure."""
    
    for group, axes in output_data.items():
        for axis, properties in axes.items():
            write_axis(output_file, group, axis, properties)

def get_data(line):
    """Cleans up and splits the line of data."""
    while '  ' in line:
        line = line.replace('  ', ' ')
    return line.split(' ')

def process_stability_derivatives(stab_file, output_file, params):
    """Processes stability derivatives from input file and writes XML formatted output."""
    data = []
    stability_vars = ['mach', 'alpha', 'beta', 'cmlp', 'cmlr', 'cmma', 'cmmb', 'cmmq', 'cmnb', 'cmnr', 'cmnp', 'cfyp', 'cfyr']
    current_data = {var: -9999 for var in stability_vars}
    
    line = stab_file.readline()
    while line:
        line_arr = get_data(line)

        # Parse the line based on its prefix
        if line.startswith("Mach_"):
            current_data['mach'] = float(line[21:33])
        elif line.startswith("AoA_"):
            current_data['alpha'] = float(line[21:33])
        elif line.startswith("Beta_"):
            current_data['beta'] = float(line[21:33])
        elif line.startswith("CMx"):
            current_data['cmlp'] = float(line_arr[4])
            current_data['cmlr'] = float(line_arr[6])
        elif line.startswith("CMy"):
            current_data['cmma'] = float(line_arr[2])
            current_data['cmmq'] = float(line_arr[5])
        elif line.startswith("CMz"):
            current_data['cmnb'] = float(line_arr[3])
            current_data['cmnr'] = float(line_arr[4])
            current_data['cmnp'] = float(line_arr[6])
        elif line.startswith("CS"):
            current_data['cfyp'] = float(line_arr[4])
            current_data['cfyr'] = float(line_arr[6])

        elif line.startswith("# Result"):
            data.append(current_data.copy())
            current_data = {var: -9999 for var in stability_vars}

        line = stab_file.readline()

    stab_file.close()

    # Generate XML output
    generate_stability_xml_output(data, output_file, params)

def generate_stability_xml_output(data, output_file, params):
    """Generates XML output based on processed data."""
    # Extract unique mach, alpha, and beta values
    mach_arr = sorted(set(d['mach'] for d in data))
    alpha_arr = sorted(set(d['alpha'] for d in data))
    beta_arr = sorted(set(d['beta'] for d in data))

    output_coeffs = {
        'cmlp': ['Roll damping derivative', 'aero/pb'],
        'cmlr': ['Roll moment due to yaw rate', 'aero/rb'],
        'cmmq': ['Pitch damping derivative', 'aero/qb'],
        'cmma': ['Pitch moment alpha dot', 'aero/alphadot-rad_sec'],
        'cmnp': ['Yaw moment due to roll rate', 'aero/pb'],
        'cmnr': ['Yaw damping derivative', 'aero/rb'],
        'cfyp': ['Side force due to roll rate', 'aero/pb'],
        'cfyr': ['Side force due to yaw rate', 'aero/rb'],
    }

    for coeff in output_coeffs:
        output_file.write(f'  <function name="aero/s/{coeff}">\n')
        output_file.write(f'    <description>{output_coeffs[coeff][0]}</description>\n')
        output_file.write('    <product>\n')
        output_file.write(f'      <property>{output_coeffs[coeff][1]}</property>\n')
        output_file.write('      <table>\n')
        output_file.write('        <independentVar lookup="row">velocities/mach</independentVar>\n')
        output_file.write('        <independentVar lookup="column">aero/alpha-deg</independentVar>\n')
        output_file.write('        <independentVar lookup="table">aero/beta-deg</independentVar>\n')

        # Output each beta point as a separate table data section
        for beta in beta_arr:
            output_file.write(f'        <tableData breakPoint="{beta:.1f}">\n')
            output_file.write('                ')
            # Write AoA column headers
            for alpha in alpha_arr:
                output_file.write(f'{alpha:10.1f}   ')
            output_file.write('\n')
            # Write each Mach row under the AoA headers
            for mach in mach_arr:
                output_file.write(f'           {mach:.3f}   ')
                for alpha in alpha_arr:
                    # Find the corresponding data entry
                    values = [d for d in data if d['mach'] == mach and d['beta'] == beta]
                    if values:
                        value = next((v[coeff] for v in values if v['alpha'] == alpha), 0)
                        output_file.write(f'{value:10.4f}   ')
                    else:
                        output_file.write('    0.0000   ')
                output_file.write('\n')
            output_file.write('        </tableData>\n')

        output_file.write('      </table>\n')
        output_file.write('    </product>\n')
        output_file.write('  </function>\n\n')




# Read parameters from a configuration file
with open('./runparams.jsonc', 'r') as param_file:
    params = commentjson.load(param_file)

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
for file_name, config_paths in params['files'].items():
    config_texts = {}
    for config_path in config_paths:
        print(f"Processing data from {config_path} filename {file_name}")

        # Move up one directory level to get the deflection angle directory
        deflection_angle_dir = os.path.basename(os.path.dirname(config_path))
        history_file_path = os.path.join(config_path, params['vspname'] + '.history')
        
        with open(history_file_path, 'r') as file:
            print(f"Processing data from {history_file_path}")
            config_texts[deflection_angle_dir] = file.readlines()

    input_txt[file_name] = config_texts


    input_txt[file_name] = config_texts

# print(f"input_txt: {input_txt}")

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
    print(f"Processing data for {s}")
    db[s] = {}
    for p, lines in files.items():
        db[s][p] = []
        for i, line in enumerate(lines):
            if line.startswith('Solver Case:'):
                data_line = lines[i + 2 + wake_iterations]
                parsed_data = parse_data_line(data_line, wake_iterations)
                dataset = dict(zip(data_order, parsed_data))
                db[s][p].append(dataset)

# Save database to file so we can review if needed
with open('./output/dataset.json', 'w+') as jf:
    json.dump(db, jf, sort_keys=True, indent=4)

# The following part of the script generates JSBSim configuration files.
# It constructs XML entries for each datapoint across various runs and positions.
# The script handles formatting, adjustment of small numbers, and XML structuring.

desc = '''
<!-- 
Generated by vsp2jsbsim.py
Author: Juttner Domokos
Based on the work of Richard Harrison
-->
<aerodynamics>

  <function name="aero/beta-deg-abs">
    <description>Beta absolute value</description>
    <abs>
      <property>aero/beta-deg</property>
    </abs>
  </function>

  <function name="aero/pb">
    <description>PB Denormalization</description>
    <product>
      <property>aero/bi2vel</property>
      <property>velocities/p-aero-rad_sec</property>
    </product>
  </function>

  <function name="aero/qb">
    <description>For denormalization</description>
    <product>
      <property>aero/ci2vel</property>
      <property>velocities/q-aero-rad_sec</property>
    </product>
  </function>

  <function name="aero/rb">
    <description>For denormalization</description>
    <product>
      <property>aero/bi2vel</property>
      <property>velocities/r-aero-rad_sec</property>
    </product>
  </function>

'''
output_file.write(desc)

output_data = params["data_to_axis_map"]

# load sorted database
db = load_database()

# Process the data points
process_data_in_database(output_file, output_data, db)


#################################################################
# Ground effect
#################################################################

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

#################################################################

#################################################################
# Stability Derivatives
#################################################################

process_stability_derivatives(stab_file, output_file, params)

#################################################################

# Take all the defined aero functions in the xml file and assign them to an axis
output_data = params['run_data_to_axis']
assign_aerodynamics_to_axis(output_file, output_data)


output_file.write('</aerodynamics>\n')
output_file.close()
output_data_file.close()
print('process time:', time.process_time())
