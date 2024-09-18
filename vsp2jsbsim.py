#!/usr/bin/env python3
import argparse
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
        print(f"mach_aoa_data: {mach_aoa_data}")
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



def process_data_in_database(output_file, output_data, db, params):
    """Processes each data point to generate XML structures."""
    for datapoint in output_data:
        print('#####', datapoint)
        output_file.write(f'  <!-- {datapoint.upper()} -->\n')
        for control_group in output_data[datapoint]:
            output_file.write(f'  <!-- {control_group} -->\n')
            for pos in output_data[datapoint][control_group]:
                print(pos)
                # betas = sorted(set(float(d['beta']) for d in db[run][pos]))

                # Generate or update entries in the output data structure
                print(f"Processing data for {datapoint} {control_group} {pos}")
                for d in db[control_group][pos]:
                    beta = format_value(float(d['Beta']), 1)
                    mach = format_value(float(d['Mach']), 3)
                    aoa = format_value(float(d['AoA']), 3)
                    value = small_number_check(float(f"{d[datapoint]:.5f}"))

                    # TODO: put this back
                    if control_group != 'base':
                        # base_value = small_number_check(float(output_data[datapoint]['base'][0][beta][mach][aoa]))
                        base_value = small_number_check(float(output_data[datapoint]['base']['0'][beta][mach][aoa]))
                        value -= base_value
                    output_data[datapoint][control_group][pos].setdefault(beta, {}).setdefault(mach, {})[aoa] = format_value(value)

                # Write to JSON after updating data
                with open('./outputData.json', 'w+') as jf:
                    json.dump(output_data, jf, sort_keys=True, indent=4)

                # Handle XML generation for this data point
                if control_group == 'ground_effect':
                    continue

                print(pos)
                # pos_str = f"{pos:.1f}"
                func_name = f'aero/{datapoint}_{control_group}_{pos.replace("-", "n")}' if control_group != 'base' else f'aero/{datapoint}_{control_group}'
                output_file.write(f'  <function name="{func_name}">\n')
                output_file.write('    <table>\n')
                output_file.write('      <independentVar lookup="row">velocities/mach</independentVar>\n')
                output_file.write('      <independentVar lookup="column">aero/alpha-deg</independentVar>\n')
                output_file.write('      <independentVar lookup="table">aero/beta-deg</independentVar>\n')
                append_beta_data(output_file, datapoint, control_group, pos, output_data, db)
                output_file.write('    </table>\n')
                output_file.write('  </function>\n\n')

            # Handling interpolation for non-base and non-ground effect data
            if control_group not in ['base', 'ground_effect']:
                interpolate_data_points(output_file, datapoint, control_group, output_data)

def interpolate_data_points(output_file, datapoint, run, output_data):
    """Creates interpolation functions for aerodynamic data points."""
    output_file.write(f'  <function name="aero/{datapoint}_{run}">\n')
    output_file.write('    <interpolate1d>\n')
    property_path = 'position/h-agl-m' if run == 'ground_effect' else f'fcs/surfaces/{run}-pos-deg'
    output_file.write(f'      <property>{property_path}</property>\n')
    
    # Sorting and interpolating data based on position
    positions = sorted(output_data[datapoint][run])
    print('positions:', positions)
    last_position = None
    for position in positions:
        position = float(position)
        print(f"position: {position}")
        # if last_position is None or last_position < 0 and position > 0:
        #     output_file.write('      <value>0</value> <value>0</value>\n')
        pos_str = f"{position:.1f}"
        print(pos_str)
        pos_str = pos_str.replace("-","n")
        print(pos_str)
        output_file.write(f'      <value>{position}</value> <property>aero/{datapoint}_{run}_{pos_str.replace("-", "n")}</property>\n')
        last_position = position

    print('last_position:', last_position)
    # if float(last_position) < 0:
    #     output_file.write('      <value>0</value> <value>0</value>\n')
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
{extra_properties}{properties_block}      </product>
    </function>
  </axis>
"""

    # Conditional string inclusion based on specific criteria
    if group == 'moments':
        if axis == 'pitch' or axis == 'roll':
            extra_properties = '        <property>metrics/bw-ft</property>\n'
        elif axis == 'yaw':
            extra_properties = '        <property>metrics/cbarw-ft</property>\n'
        else:
            extra_properties = ''
    else:
        extra_properties = ''

    # Compose the property elements from the provided properties
    property_elements = '\n'.join(f'          <property>{prop}</property>' for prop in properties)

    # Conditional inclusion of <sum> tag
    if len(properties) > 1:
        properties_block = '        <sum>\n{0}\n        </sum>\n'.format(property_elements)
    else:
        properties_block = property_elements + '\n'

    # Fill the template with actual data
    formatted_axis = axis_template.format(
        axis_name=axis.upper(),
        group=group,
        axis=axis,
        extra_properties=extra_properties,
        properties_block=properties_block
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
    print(f"mach_arr: {mach_arr}")
    print(f"alpha_arr: {alpha_arr}")
    print(f"beta_arr: {beta_arr}")

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
        # Loop through each beta value
        for beta in beta_arr:
            output_file.write(f'        <tableData breakPoint="{beta:.1f}">\n')
            output_file.write('                ')
            
            # Write AoA (Angle of Attack) column headers
            for alpha in alpha_arr:
                output_file.write(f'{alpha:10.1f}   ')
            output_file.write('\n')
            
            # Write each Mach row under the AoA headers
            for mach in mach_arr:
                output_file.write(f'           {mach:.3f}   ')
                
                # Loop through each AoA value
                for alpha in alpha_arr:
                    # Filter the data to find entries that match the current Mach and beta values
                    filtered_data = []
                    for entry in data:  # Iterate over all data entries
                        # Check if 'mach' and 'beta' values match the current Mach and beta
                        if entry['mach'] == mach and entry['beta'] == beta:
                            filtered_data.append(entry)  # Add matching entry to filtered_data
                        else:
                            print(f"entry['mach'] {entry['mach']} != mach {mach} or entry['beta'] {entry['beta']} != beta {beta}")
                    
                    # Find the corresponding data entry for the current alpha
                    # Check if there are any entries in the filtered_data
                    if filtered_data:
                        # Find the corresponding value for the current alpha
                        # This generator expression searches for the first entry in filtered_data with a matching alpha value
                        value = next(
                            (
                                v[coeff]  # Extract the value for the given coefficient
                                for v in filtered_data  # Iterate over each entry in the filtered_data
                                if v['alpha'] == alpha  # Check if the alpha value matches the current alpha
                            ),
                            0  # Default value if no match is found
                        )
                        # Write the value to the output file, formatted to 4 decimal places
                        output_file.write(f'{value:10.4f}   ')
                    else:
                        # If no matching entries are found, write a default value of 0.0000
                        output_file.write('    0.0000   ')

                output_file.write('\n')
            
            output_file.write('        </tableData>\n')

        output_file.write('      </table>\n')
        output_file.write('    </product>\n')
        output_file.write('  </function>\n\n')


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Process some integers.")
    
    # Adding optional arguments
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('-w', '--wake_iterations', type=int, default=3, help='Number of wake iterations')
    parser.add_argument('--runparams', '-p', help='runparams.jsonc file', default='./runparams.jsonc', type=str)

    args = parser.parse_args()

    DEBUG = args.debug
    wake_iterations = args.wake_iterations

    # Read parameters from a configuration file
    with open(args.runparams, 'r') as param_file:
        params = commentjson.load(param_file)

    # Prepare output files
    output_json_path = './output/outputData.json'
    output_data_file = open(output_json_path, 'w+')
    output_file = open(params['output_file'], 'w+')


    input_base = params['base_file']
    input_base_path = os.path.join(input_base, params['vspname'] + '_DegenGeom.history')
    input_txt_base = open(input_base_path, 'r').readlines()
    input_txt = {}


    # Parse the history files for each run configuration
    for control_group in params['deflection_cases']:
        deflection_angles = params['deflection_cases'][control_group]
        input_txt[control_group] = {}    
        for deflection_angle in deflection_angles:
            print(f"finding data for {control_group} with deflection angle {deflection_angle}")
            defflection_angle_str = f"{deflection_angle:.1f}"
            history_file_path = os.path.join('output', control_group, defflection_angle_str, params['vspname'] + '_DegenGeom.history')
            with open(history_file_path, 'r') as file:
                print(f"found data from {history_file_path} deflection angle {defflection_angle_str}") 
                input_txt[control_group][defflection_angle_str] = file.readlines()
                # input_txt[control_group][str(deflection_angle)] = ""


    # Database for storing parsed data
    
    db = {'base': {0: []}}

    #               Mach, AoA, Beta, CLo,CLi, CLtot, CDo, CDi, CDtot, CDt, CDtot_t, CSo, CSi, CStot, L/D, E, CFxo, CFyo, CFzo, CFxi, CFyi, CFzi, CFxtot, CFytot, CFztot, CMxo, CMyo, CMzo, CMxi, CMyi, CMzi, CMxtot, CMytot, CMztot, T/QS 
    # data_order = ['Mach', 'AoA', 'beta', 'CL', 'CDo', 'CDi', 'CDtot', 'CS', 'L/D', 'E', 'CFx', 'CFz', 'CFy', 'CMx', 'CMy', 'CMz', 'T/QS']
    data_order = ['Mach', 'AoA', 'Beta', 'CLo','CLi', 'CLtot', 'CDo', 'CDi', 'CDtot', 'CDt', 'CDtot_t', 'CSo', 'CSi', 'CStot', 'L/D', 'E', 'CFxo', 'CFyo', 'CFzo', 'CFxi', 'CFyi', 'CFzi', 'CFxtot', 'CFytot', 'CFztot', 'CMxo', 'CMyo', 'CMzo', 'CMxi', 'CMyi', 'CMzi', 'CMxtot', 'CMytot', 'CMztot', 'T/QS' ]
    # print(json.dumps(input_txt, indent=4))

    # Process the base file data
    print(f"Processing base data from {input_base_path}")
    for i, line in enumerate(input_txt_base):
        if line.startswith('Solver Case:'):
            data_line = input_txt_base[i + 2 + wake_iterations]
            parsed_data = parse_data_line(data_line, wake_iterations)
            dataset = dict(zip(data_order, parsed_data))
            db['base'][0].append(dataset)

    # Process data for each deflection case
    for control_group in input_txt:
        print(f"Processing data for {control_group}")
        db[control_group] = {}
        for deflection_angle in input_txt[control_group]:
            print(f"Processing data for {control_group} with deflection angle {deflection_angle}")
            db[control_group][deflection_angle] = []
            lines = input_txt[control_group][deflection_angle]
            for i, line in enumerate(lines):
                if line.startswith('Solver Case:'):
                    data_line = lines[i + 2 + wake_iterations]
                    parsed_data = parse_data_line(data_line, wake_iterations)
                    dataset = dict(zip(data_order, parsed_data))
                    db[control_group][deflection_angle].append(dataset)

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
    process_data_in_database(output_file, output_data, db, params)


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


    # Open the stability file and base history file
    stab_file_path = os.path.join(params['stab_file'], params['vspname'] + '_DegenGeom.stab')
    stab_file = open(stab_file_path, 'r')
    process_stability_derivatives(stab_file, output_file, params)

    #################################################################

    # Take all the defined aero functions in the xml file and assign them to an axis
    output_data = params['run_data_to_axis']
    assign_aerodynamics_to_axis(output_file, output_data)


    output_file.write('</aerodynamics>\n')
    output_file.close()
    output_data_file.close()
    print('process time:', time.process_time())
