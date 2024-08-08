#!./vsp-venv/bin/python3
import commentjson
import json
import subprocess
import sys
import signal
import time
import argparse
import os 
import shutil
from datetime import datetime
from os import path
from openvsp import vsp

def interrupthandler(signal, frame):
    """
    Handles interruption signals by saving progress to a file.

    Args:
        signal: The signal number.
        frame: The current stack frame.
    """
    if progress['isused']:
        with open(args.progressfile, 'w+') as jf:
            jf.write(json.dumps(progress, sort_keys=True, indent=4))
        exit(0)

def vprint(text):
    """
    Verbose print, outputs text only if verbose mode is active.

    Args:
        text (str): The text to print.
    """
    if args.verbose:
        print(text)



# this is basically just copying the base DegenGeom and VSP3. might refactor this later
def create_degengeom_and_vsp3(case_dir: str, src_file_path: str, vspfile: str , name : str, manual=False, pos=0):
    """
    Generates DegenGeom CSV and .vsp3 files based on the provided configurations.

    Args:
        case_dir (str): Directory location to store output.
        src_file_path (str): Source file path.
        vspfile (str): Path to the .vsp3 file.
        name (str): name of Geometry to manipulate. 
        manual (bool): Whether manual adjustments are needed.
        pos (int): Position adjustment if manual is True.
    """
    if not path.exists(case_dir):
        os.makedirs(case_dir)

    # remove old outputs
    if name in params['surf_names']:
        name = params['surf_names'][name]

    try:
        os.remove(f"{case_dir}/{params['vspname']}_DegenGeom.csv")
    except FileNotFoundError:
        pass

    if not args.dryrun:
        try:
            print(f"removing {case_dir}/{params['vspname']}_DegenGeom.history")
            os.remove(f"{case_dir}/{params['vspname']}_DegenGeom.history")
        except FileNotFoundError:
            pass
        if 'stab' in case_dir:
            try:    
                os.remove(case_dir + '/' + params['vspname'] + '_DegenGeom.stab')
            except FileNotFoundError:
                pass


    print(f"reading vspfile {src_file_path}/{vspfile}")
    vsp.ReadVSPFile(f"{src_file_path}/{vspfile}")
    vsp.SetVSP3FileName(f"{case_dir}/{vspfile}")

    # not sure if I want to keep this #########################
    # if manual:
    #     print(name)
    #     geom_id = vsp.FindGeomsWithName(name)[0]
    #     for p in vsp.GetGeomParmIDs(geom_id):
    #         if vsp.GetParmName(p) == 'Y_Rotation':
    #             print('rotating by', pos)
    #             vsp.SetParmVal(p, float(pos))
    #             break
    #     for n in vsp.GetAllSubSurfIDs():
    #         vsp.DeleteSubSurf(n)
    # else:
    #     for n in vsp.GetAllSubSurfIDs():
    #         if name != vsp.GetSubSurfName(n):
    #             vsp.DeleteSubSurf(n)
    #         else:
    #             vprint(name + ' ' + vsp.GetSubSurfName(n))
    ##########################################################

    print('writing out', case_dir + '/' + vspfile[:-5] + '.csv')
    vsp.ComputeDegenGeom(vsp.SET_ALL, vsp.DEGEN_GEOM_CSV_TYPE)
    print(f"writing vsp3 file: {case_dir}/{params['vspname']}_DegenGeom_{name}.vsp3")
    vsp.WriteVSPFile(f"{case_dir}/{params['vspname']}_DegenGeom_{name}.vsp3")
    vsp.ClearVSPModel()

    if args.cleanup:
        print('cleaning...')
        filename = case_dir + '/' + params['vspname'] + '_DegenGeom.'
        for ext in ['adb', 'adb.cases', 'fem', 'group.1', 'lod', 'polar']:
            os.remove(filename + ext)


def update_vsp_configuration(params: dict, baseprops: dict, configprops: dict, controlConfig: dict, postprops: dict, args, progress: dict, ignore_list: list, only_list: list, dry_run=False):
    """
    Process a VSP model and generate aero data based on the provided configurations.
    
    Args:
        params (dict): Parameters including file paths and other configurations.
        baseprops (dict): Base properties for the VSP configuration.
        configprops (dict): Configuration properties specific to the base configuration.
        controlConfig (dict): Control surface configurations.
        postprops (dict): Properties to be applied after the base configuration.
        args: Script arguments for execution controls.
        progress (dict): Dictionary to track progress of completed tasks.
        ignore_list (list): List of cases to ignore.
        only_list (list): List of cases to exclusively include.
    """
    for case in ['est', 'base', 'stab']:
        case_file_path = params[case + '_file']
        vspaero_filename = params['vspname'] + '_DegenGeom.vspaero'

        # Skip cases based on ignore_list and only_list
        if case in ignore_list or (only_list and case not in only_list):
            continue
        
        # Check if the case has been completed before
        if case_file_path + params['vsp3_file'][:-5] not in progress['completed']:
            # Create directory if it does not exist
            if not os.path.exists(case_file_path):
                os.makedirs(case_file_path)
            
            nochange = True
            old_content = read_file_content(case_file_path + vspaero_filename)

            # Write new configuration based on properties
            write_vsp_configuration(case_file_path, vspaero_filename, params, baseprops, configprops, controlConfig, postprops, case)
            
            new_content = read_file_content(case_file_path + vspaero_filename)
            if new_content != old_content:
                nochange = False

            old_csv_content = read_file_content(case_file_path + params['vspname'] + '_DegenGeom.csv')
            
            # Generate new data if needed
            if new_content != old_csv_content or case == 'est':
                nochange = False

            # if not nochange or args.force:
            run_solver(case, case_file_path, args, progress)

def read_file_content(file_path: str) -> list:
    """Read file content if file exists, otherwise return None."""
    try:
        with open(file_path, 'r') as file:
            return file.readlines()
    except FileNotFoundError:
        return None

def write_vsp_configuration(case_file_path: str, vspaero_filename: str, params: dict, baseprops: dict, configprops: dict, controlConfig: dict, postprops: dict, case: str):
    """Write VSP configuration to file."""

    print(f'Writing VSP configuration for case: {case}, file: {case_file_path + vspaero_filename}')
    with open(case_file_path + vspaero_filename, 'w') as file:
        for p, value in baseprops.items():
            file.write(f'{p} = {value}\n')
        for p, value in configprops['base'].items():
            file.write(f'{p} = {value}\n')

        # not sure what this is for
        for p, value in postprops.items():
            file.write(f'{p} = {value}\n')
        
        # write surface deflection configurations
        for control_group in controlConfig:
            file.write(f"{control_group['group_name']}\n")
            file.write(f"{', '.join(control_group['surface_names'])}\n")
            file.write(f"{', '.join([str(g) for g in control_group['gains']])}\n")
            file.write(f"{control_group['deflection']}\n")

    create_degengeom_and_vsp3(case_file_path, params['vsp_filepath'], params['vsp3_file'], str(case))

def run_solver(case: str, case_file_path: str, args, progress: dict):
    """Run solver for the VSP model based on the case."""
    print(f'Running solver for case: {case}')


    # TODO: make this less WET
    if not args.dryrun or case == 'est':
        if os.name == 'posix':
            if case == 'est':
                cmd = ['vspaero', '-omp', args.jobs, params['vspname'] + '_DegenGeom']
                print(f"Running command: {cmd}, cwd: {case_file_path}")
                subprocess.run(cmd, cwd=case_file_path, check=True)
                
            else:
                cmd = ['vspaero', '-omp', args.jobs, '-stab', params['vspname'] + '_DegenGeom']
                print("running cmd")
                print(cmd)
                print(f"path: {case_file_path}")
                subprocess.run(cmd, cwd=case_file_path, check=True)
                

        elif os.name == 'nt':
            try:
                vsp_exe_rel = 'OpenVSP-3.38.0-win64\\vspaero.exe'
                vsp_abs_path = os.path.abspath(vsp_exe_rel)
                if case == 'est':
                    cmd = [vsp_abs_path, '-omp', args.jobs, params['vspname'] + '_DegenGeom']
                    print(f"Running command: {cmd}, cwd: {case_file_path}")
                    subprocess.run(cmd, cwd=case_file_path, shell=True, check=True)
                else:
                    cmd = [vsp_abs_path, '-omp', args.jobs, '-stab', params['vspname'] + '_DegenGeom']
                    print(f"Running command: {cmd}, cwd: {case_file_path}")
                    subprocess.run(cmd, cwd=case_file_path, shell=True, check=True)
            except subprocess.CalledProcessError as e:
                # Print an error message and exit the program with a non-zero status
                print(f"Command '{e.cmd}' failed with exit status {e.returncode}")
                sys.exit(e.returncode)



        progress['completed'].append(case_file_path + params['vsp3_file'][:-5])

def run_deflection_cases(params: dict, baseprops: dict, progress: dict, ignore_list: list, only_list: list, args):
    """
    Process each VSP file according to the configurations and run simulations if necessary.

    Args:
        params (dict): Contains various parameters including file paths and configurations.
        baseprops (dict): Base properties for setting up VSP files.
        progress (dict): Tracks which files have been completely processed.
        ignore_list (list): List of runs to ignore.
        only_list (list): List of runs to exclusively include.
        args: Contains runtime arguments such as job numbers and force flags.
    """
    for control_group in params['deflection_cases']:
        
        # not sure if this works
        # Skip runs based on ignore_list and only_list 
        if control_group in ignore_list or (only_list and control_group not in only_list):
            continue

        for case in params['deflection_cases'][control_group]:
            # assuming control_group name is file safe
            case_file_path = f"output/{control_group}/{case}/"
            # case_file_path = case + params['vsp3_file'][:-5]
            if case_file_path not in progress['completed']:
                # vsp_filename = case + params['vspname'] + '_DegenGeom.vspaero'
                vspaero_filename = f"{params['vspname']}_DegenGeom.vspaero"
                vspaero_txt = read_or_copy_vspaero_file(case_file_path, vspaero_filename, params)
                vspaero_txt = update_vspaero_content(vspaero_txt, baseprops, params, control_group)
                nochange = write_vspaero_file(case_file_path, vspaero_filename, vspaero_txt)
                nochange &= update_csv_if_needed( f"{case_file_path}", params, control_group)

                # if not nochange or args.force:
                print(f"Running solver for case: {case}")
                run_solver(case, case_file_path, args, progress)  # Assuming your 'run_solver' doesn't need 'case_file_path'

                progress['completed'].append(case_file_path)

def read_or_copy_vspaero_file(case_file_path: str, filename: str, params: dict) -> list:
    """ Attempts to the .vspaero file for a case. if not, creates one based on the base case """
    
    full_vspaero_case_file_path = f"{case_file_path}/{filename}"
    if not os.path.exists(f"{full_vspaero_case_file_path}"):
        src_file = f"{params['vsp_filepath']}/{params['vspname']}_DegenGeom.vspaero"
        print(f"Copying {src_file} to {full_vspaero_case_file_path}")
        shutil.copy(src_file, full_vspaero_case_file_path)
    
    with open(full_vspaero_case_file_path, 'r') as file:
        return file.readlines()

def update_vspaero_content(vspaero_txt: list, baseprops: dict, params: dict, run: str) -> list:
    """ Updates VSP content based on run and base properties. """
    output = []
    for entry in baseprops:
        if entry == 'ClMax' and run in params['CLmax']:
            output.append(f"{entry} = {params['CLmax'][run]}\n")
        elif entry == 'Beta' and run in params['alpha_only']:
            output.append("Beta = 0\n")
        else:
            output.append(f"{entry} = {baseprops[entry]}\n")
    output.extend(vspaero_txt[len(baseprops):])
    return output

def write_vspaero_file(case_file_path: str, vspaero_filename: str, vspaero_config: list) -> bool:
    """ Writes vspaero_txt to a file and checks if it changed. If changed
    the function returns False, otherwise True.
    
    Args:
        case_file_path (str): Directory location to store output.
        vspaero_filename (str): File name to write to.
        vspaero_config (list): Configuration to write to the file.

    Returns:
        nochange bool: True if there was no change, False if there was a change.

    """

    # with open(vspaero_filename, 'r') as file:
    #     old_vspaero_config = file.readlines()

    # if old_vspaero_config == vspaero_config:
    #     return True

    print(f"Writing VSPAERO configuration to file: {case_file_path}/{vspaero_filename}")
    with open(f"{case_file_path}/{vspaero_filename}", 'w') as file:
        file.writelines(vspaero_config)
    
    return False

def update_csv_if_needed(case_dir: str, params: dict, run: str) -> bool:
    """ Updates CSV if required and checks for changes. 
    
        Returns: nochange bool: True if there was no change, False if there was a change.
    """
    csv_filename = f"{case_dir}{params['vspname']}_DegenGeom.csv"

    # TODO implement the change check
    # old_content = read_or_copy_vspaero_file(csv_filename, {})
    if run not in params['manual_set']:
        create_degengeom_and_vsp3(case_dir, params['vsp_filepath'], params['vsp3_file'], run)
    else:
        # this case probable doesn't work
        create_degengeom_and_vsp3(case_dir, params['vsp3_file'], params['manual_set'][run], True, int(run.split('/')[-2]))
    # new_content = read_or_copy_vspaero_file(csv_filename, {})
    return True

def read_control_groups(lines, num_control_groups):


    control_groups = []

    for i in range(num_control_groups):
        control_group = dict()
        control_group['group_name'] = lines[i*4].strip()
        
        surface_names = lines[i*4 + 1].strip().split(',')
        for j in range(len(surface_names)):
            surface_names[j] = surface_names[j].strip()
        control_group['surface_names'] = surface_names

        control_group['num_surfaces'] = len(surface_names)

        gains = lines[i*4 + 2].strip().split(',')
        for j in range(len(gains)):
            gains[j] = float(gains[j].strip())
        control_group['gains'] = gains 
        
        control_group['deflection'] = float(lines[i*4 + 3].strip())
        print(control_group)
        control_groups.append(control_group)

    return control_groups


# Read parameters from a JSON file.
with open('./runparams.jsonc', 'r') as p:
    params = commentjson.loads(p.read())

# Set up command line argument parsing.
parser = argparse.ArgumentParser(description="Script to run VSPAERO with various options.")
parser.add_argument('--dryrun', '-d', help='Execute without running VSPAERO', action='store_true')
parser.add_argument('--cleanup', '-c', help='Remove all files but .lod, .history, and .stab', action='store_true')
parser.add_argument('--verbose', '-v', help='Increase verbosity', action='store_true')
parser.add_argument('--resolution', '-r', help='Set resolution of run', choices=['low', 'medium', 'high'], default='low')
parser.add_argument('--jobs', '-j', help='-omp setting of VSPAERO', default='1', type=str)
parser.add_argument('--wake', '-w', help='Number of wake iterations', default=3, type=int)
parser.add_argument('--force', '-f', help='Re-compute everything', action='store_true')
parser.add_argument('--ignore', '-i', help='Cases to skip, comma separated', metavar='FOO,BAR')
parser.add_argument('--only', '-o', help='Only run these cases, comma separated', metavar='FOO,BAR')
parser.add_argument('--progressfile', type=str)
args = parser.parse_args()

# Check for conflicting options.
if args.ignore is not None and args.only is not None:
    print('Cannot use --only and --ignore at the same time')
    exit()

ignore_list = args.ignore.split(',') if args.ignore is not None else []
only_list = args.only.split(',') if args.only is not None else []

progress = {
    "isused": "False",
    "done": "False",
    "dryrun": "False",
    "verbose": "False",
    "cleanup": "False",
    "nproc": 2,
    "wake": 3,
    "completed": []
}

# Load progress from file if specified.
if args.progressfile is not None:
    with open(args.progressfile) as pf:
        progress = json.loads(pf.read())
        progress['isused'] = True
else:
    args.progressfile = 'progress.json'

if not progress['completed']:
    progress['done'] = False


baseprops = dict()

controlConfig = []


with open(params['vsp_filepath'] + '/' + params['vspname'] + '_DegenGeom.vspaero', 'r') as v:
    print(f"reading {params['vsp_filepath'] + '/' + params['vspname'] + '_DegenGeom.vspaero'}")
    lines = v.readlines()

row_number = 0
while row_number < len(lines):
    line = lines[row_number]
    print(line)
    if "NumberOfControlGroups =" in line:
        name, num_control_groups_str = line.split('=')
        print(f"Number of control groups: {num_control_groups_str.strip()}")
        num_control_groups = int(num_control_groups_str.strip())
        control_group_lines = lines[row_number + 1:row_number + 1 + num_control_groups*4]
        print(control_group_lines)
        # Handle the special condition
        controlConfig = read_control_groups(control_group_lines, num_control_groups)
        row_number += num_control_groups*4 + 1
    else:
        try:
            name, value = line.split('=')
        except ValueError:
            # Output the problematic line to help with debugging.
            print(f"Failed to parse the line at row {row_number}: '{line.strip()}'")
            raise ValueError(f"Input line '{line.strip()}' at row {row_number} is not in the expected 'name=value' format.")

        baseprops[name.strip()] = value.strip()
        row_number += 1


baseprops["WakeIters"] = str(args.wake)

# set flow conditions set in config file
baseprops["AoA"] = params['alpha']
baseprops["Beta"] = params['beta']
baseprops["Mach"] = params['mach']

configprops = {"base": {"NumberOfControlGroups": "0"}}
# seems usefull not sure how it works
postprops = {"Preconditioner": "Matrix", "Karman-Tsien Correction": "N"}

# don't this this is needed
est_baseprops = {key: ('0.4' if key == 'Mach' else '5' if key == 'AoA' else '0' if key == 'Beta' else value) for key, value in baseprops.items()}

signal.signal(signal.SIGINT, interrupthandler)

print('Dryrun:', args.dryrun)
print('Cleanup:', args.cleanup)
STARTTIME = time.localtime()

# Run base case
update_vsp_configuration(params, baseprops, configprops, controlConfig, postprops, args, progress, ignore_list, only_list, args.dryrun)

# Run surface deflection cases
run_deflection_cases(params, baseprops, progress, ignore_list, only_list, args)


print('FINISHED')
# subprocess.run(['date'])
print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
progress['done'] = True
with open(args.progressfile, 'w+') as jf:
    jf.write(json.dumps(progress, sort_keys=True, indent=4))


