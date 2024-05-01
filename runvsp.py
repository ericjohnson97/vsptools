#!./vsp-venv/bin/python3
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


def generate(loc, vspfile, name, manual=False, pos=0):
    """
    Generates VSPAERO input files and configurations.

    Args:
        loc (str): Directory location to store output.
        vspfile (str): Path to the VSP file.
        name (str): Geometry name.
        manual (bool): Whether manual adjustments are needed.
        pos (int): Position adjustment if manual is True.
    """
    if not path.exists(loc):
        # subprocess.run(['mkdir', '-p', loc])
        os.makedirs(loc)
    # remove old outputs
    if name in params['surf_names']:
        name = params['surf_names'][name]
    # subprocess.run(['rm', loc + params['vspname'] + '.csv'])
    try:
        os.remove(loc + params['vspname'] + '.csv')
    except FileNotFoundError:
        pass

    if not args.dryrun:
        # subprocess.run(['rm', loc + params['vspname'] + '.history'])
        try:
            os.remove(loc + params['vspname'] + '.history')
        except FileNotFoundError:
            pass
        if 'stab' in loc:
            # subprocess.run(['rm', loc + params['vspname'] + '.stab'])
            try:    
                os.remove(loc + params['vspname'] + '.stab')
            except FileNotFoundError:
                pass


    vsp.ReadVSPFile(vspfile)
    vsp.SetVSP3FileName(loc + vspfile)

    if manual:
        print(name)
        geom_id = vsp.FindGeomsWithName(name)[0]
        for p in vsp.GetGeomParmIDs(geom_id):
            if vsp.GetParmName(p) == 'Y_Rotation':
                print('rotating by', pos)
                vsp.SetParmVal(p, float(pos))
                break
        for n in vsp.GetAllSubSurfIDs():
            vsp.DeleteSubSurf(n)
    else:
        for n in vsp.GetAllSubSurfIDs():
            if name != vsp.GetSubSurfName(n):
                vsp.DeleteSubSurf(n)
            else:
                vprint(name + ' ' + vsp.GetSubSurfName(n))

    print('writing out', loc + vspfile[:-5] + '.csv')
    vsp.ComputeDegenGeom(vsp.SET_ALL, vsp.DEGEN_GEOM_CSV_TYPE)
    vsp.WriteVSPFile(loc + params['vspname'] + name + '.vsp3')
    vsp.ClearVSPModel()

    if args.cleanup:
        print('cleaning...')
        fn = loc + params['vspname'] + '.'
        for ext in ['adb', 'adb.cases', 'fem', 'group.1', 'lod', 'polar']:
            # subprocess.run(['rm', fn + ext])
            os.remove(fn + ext)


def update_vsp_configuration(params: dict, baseprops: dict, configprops: dict, postprops: dict, args, progress: dict, ignore_list: list, only_list: list, dry_run=False):
    """
    Process a VSP model and generate aero data based on the provided configurations.
    
    Args:
        params (dict): Parameters including file paths and other configurations.
        baseprops (dict): Base properties for the VSP configuration.
        configprops (dict): Configuration properties specific to the base configuration.
        postprops (dict): Properties to be applied after the base configuration.
        args: Script arguments for execution controls.
        progress (dict): Dictionary to track progress of completed tasks.
        ignore_list (list): List of cases to ignore.
        only_list (list): List of cases to exclusively include.
    """
    for case in ['est', 'base', 'stab']:
        case_file_path = params[case + '_file']
        vsp_filename = params['vspname'] + '.vspaero'

        # Skip cases based on ignore_list and only_list
        if case in ignore_list or (only_list and case not in only_list):
            continue
        
        # Check if the case has been completed before
        if case_file_path + params['vsp3_file'][:-5] not in progress['completed']:
            # Create directory if it does not exist
            if not os.path.exists(case_file_path):
                os.makedirs(case_file_path)
            
            nochange = True
            old_content = read_file_content(case_file_path + vsp_filename)

            # Write new configuration based on properties
            write_vsp_configuration(case_file_path, vsp_filename, params, baseprops, configprops, postprops, case)
            
            new_content = read_file_content(case_file_path + vsp_filename)
            if new_content != old_content:
                nochange = False

            old_csv_content = read_file_content(case_file_path + params['vspname'] + '.csv')
            
            # Generate new data if needed
            if new_content != old_csv_content or case == 'est':
                nochange = False

            if not nochange or args.force:
                run_solver(case, case_file_path, args, progress)

def read_file_content(file_path: str) -> list:
    """Read file content if file exists, otherwise return None."""
    try:
        with open(file_path, 'r') as file:
            return file.readlines()
    except FileNotFoundError:
        return None

def write_vsp_configuration(case_file_path: str, vsp_filename: str, params: dict, baseprops: dict, configprops: dict, postprops: dict, case: str):
    """Write VSP configuration to file."""

    print(f'Writing VSP configuration for case: {case}, file: {case_file_path + vsp_filename}')
    with open(case_file_path + vsp_filename, 'w') as file:
        for p, value in baseprops.items():
            file.write(f'{p} = {value}\n')
        for p, value in configprops['base'].items():
            file.write(f'{p} = {value}\n')
        for p, value in postprops.items():
            file.write(f'{p} = {value}\n')
    generate(case_file_path, params['vsp3_file'], case)

def run_solver(case: str, case_file_path: str, args, progress: dict):
    """Run solver for the VSP model based on the case."""
    print(f'Running solver for case: {case}')
    if not args.dryrun or case == 'est':
        if os.name == 'posix':
            if case == 'est':
                subprocess.run(['bash', './run.sh', case_file_path, args.jobs, '0'])
            else:
                 subprocess.run(['bash', './runstab.sh', params[case + '_file'], args.jobs, '0'])

        elif os.name == 'nt':
            try:
                if case == 'est':
                    cmd = ['..\..\OpenVSP-3.38.0-win64\\vspaero.exe', '-omp', args.jobs, params['vspname']]
                    print(f"Running command: {cmd}, cwd: {case_file_path}")
                    subprocess.run(cmd, cwd=case_file_path, shell=True, check=True)
                else:
                    cmd = ['..\..\OpenVSP-3.38.0-win64\\vspaero.exe', '-omp', args.jobs, '-stab', params['vspname']]
                    print(f"Running command: {cmd}, cwd: {case_file_path}")
                    subprocess.run(cmd, cwd=case_file_path, shell=True, check=True)
            except subprocess.CalledProcessError as e:
                # Print an error message and exit the program with a non-zero status
                print(f"Command '{e.cmd}' failed with exit status {e.returncode}")
                sys.exit(e.returncode)



        progress['completed'].append(case_file_path + params['vsp3_file'][:-5])

def process_vsp_files(params: dict, baseprops: dict, progress: dict, ignore_list: list, only_list: list, args):
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
    for run in params['files']:
        # Skip runs based on ignore_list and only_list
        if run in ignore_list or (only_list and run not in only_list):
            continue

        for case in params['files'][run]:
            case_file_path = case + params['vsp3_file'][:-5]
            if case_file_path not in progress['completed']:
                vsp_filename = case + params['vspname'] + '.vspaero'
                vsp_txt = read_or_copy_vsp_file(vsp_filename, params)

                output = update_vsp_content(vsp_txt, baseprops, params, run)
                nochange = write_and_compare_output(vsp_filename, output)
                nochange &= update_csv_if_needed(case, params, run)

                if not nochange or args.force:
                    run_solver(case, case, args, progress)  # Assuming your 'run_solver' doesn't need 'case_file_path'

                progress['completed'].append(case_file_path)

def read_or_copy_vsp_file(filename: str, params: dict) -> list:
    """ Attempts to read a VSP file, or copies a default if not found. """
    try:
        with open(filename, 'r') as file:
            return file.readlines()
    except FileNotFoundError:
        shutil.copy(params['vspname'] + '.vspaero', filename)
        with open(filename, 'r') as file:
            return file.readlines()

def update_vsp_content(vsp_txt: list, baseprops: dict, params: dict, run: str) -> list:
    """ Updates VSP content based on run and base properties. """
    output = []
    for entry in baseprops:
        if entry == 'ClMax' and run in params['CLmax']:
            output.append(f"{entry} = {params['CLmax'][run]}\n")
        elif entry == 'Beta' and run in params['alpha_only']:
            output.append("Beta = 0\n")
        else:
            output.append(f"{entry} = {baseprops[entry]}\n")
    output.extend(vsp_txt[len(baseprops):])
    return output

def write_and_compare_output(filename: str, output: list) -> bool:
    """ Writes output to a file and checks if it changed. """
    old_content = read_or_copy_vsp_file(filename, {})
    with open(filename, 'w') as file:
        file.writelines(output)
    new_content = read_or_copy_vsp_file(filename, {})
    return new_content == old_content

def update_csv_if_needed(case: str, params: dict, run: str) -> bool:
    """ Updates CSV if required and checks for changes. """
    csv_filename = case + params['vspname'] + '.csv'
    old_content = read_or_copy_vsp_file(csv_filename, {})
    if run not in params['manual_set']:
        generate(case, params['vsp3_file'], run)
    else:
        generate(case, params['vsp3_file'], params['manual_set'][run], True, int(run.split('/')[-2]))
    new_content = read_or_copy_vsp_file(csv_filename, {})
    return new_content == old_content


# Read parameters from a JSON file.
with open('./runparams.json', 'r') as p:
    params = json.loads(p.read())

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

# Prepare Mach, AoA, and Beta strings.
mach = ""
aoa = ""
beta = "-20, -10, "
for m in range(1, 10):
    mach += f"{m * 0.1:.1f}, "
mach = mach.rstrip(", ")

for a in range(-10, 61, 5):
    aoa += f"{a}, "
aoa = aoa.rstrip(", ")

for b in range(-5, 6):
    beta += f"{b}, "
beta += "10, 20"

# Adjust Mach, AoA, and Beta based on resolution.
if args.resolution != 'high':
    mach = params['mach']
    if args.resolution == 'medium':
        aoa = params['aoa_medium']
        beta = params['beta_medium']
    else:
        aoa = params['aoa_low']
        beta = params['beta_low']

print(f"Mach: {mach}!")
print(f"AoA: {aoa}!")
print(f"Beta: {beta}!")

baseprops = dict()
reserved_names = {'Mach': mach, 'AoA': aoa, 'Beta': beta, 'ClMax': params['CLmax']['base']}

with open( params['vsp_filepath'] + params['vspname']+'.vspaero', 'r') as v:
    for line in v:
        try:
            name, value = line.split('=')
        except ValueError:
            # Output the problematic line to help with debugging.
            print(f"Failed to parse the line: '{line}'")

            # Raise a more descriptive error to halt the program or trigger further exception handling.
            raise ValueError(f"Input line '{line}' is not in the expected 'name=value' format.")


        baseprops[name.strip()] = value.strip()
        if name == 'WakeIters':
            break

print(baseprops)

baseprops["WakeIters"] = str(args.wake)
configprops = {"base": {"NumberOfControlGroups": "0"}}
postprops = {"Preconditioner": "Matrix", "Karman-Tsien Correction": "N"}

est_baseprops = {key: ('0.4' if key == 'Mach' else '5' if key == 'AoA' else '0' if key == 'Beta' else value) for key, value in baseprops.items()}

signal.signal(signal.SIGINT, interrupthandler)

print('Dryrun:', args.dryrun)
print('Cleanup:', args.cleanup)
STARTTIME = time.localtime()


update_vsp_configuration(params, baseprops, configprops, postprops, args, progress, ignore_list, only_list, args.dryrun)

process_vsp_files(params, baseprops, progress, ignore_list, only_list, args)


print('FINISHED')
# subprocess.run(['date'])
print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
progress['done'] = True
with open(args.progressfile, 'w+') as jf:
    jf.write(json.dumps(progress, sort_keys=True, indent=4))


