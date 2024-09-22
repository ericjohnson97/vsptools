### Python toolset to create JSBSim flight dynamics models with VSPAERO

Special thanks to Jüttner Domokos for publishing his work. This repository is a fork of his original work, which can be found [here](https://github.com/Rudolf339/vsptools). I have decided to build on his work and add more features that are relevant to me. I have a desire to be able to take an OpenVSP model and generate aerodynamics data for JSBSim. I have special interest in generating my JSBsim models to be compatible with both ardupilot and PX4. 

This project is a work in progress and does not work yet, but I am looking forward to working on this more in the coming months.

## Work Flow

- 1. create a .vsp3 model with control surface groups
- 2. run runvsp.py to generate aerodynamic data
- 3. run vsp2jsbsim.py to generate JSBSim model


## runvsp.py
```bash
python3 runvsp.py --help
WARNING 7: VSPAERO Viewer Not Found. 
        Expected here: /opt/conda/lib/python3.12/site-packages/openvsp/vspviewer
usage: runvsp.py [-h] [--dryrun] [--cleanup] [--verbose] [--resolution {low,medium,high}] [--jobs JOBS] [--wake WAKE] [--force] [--ignore FOO,BAR] [--only FOO,BAR]
                 [--runparams RUNPARAMS] [--progressfile PROGRESSFILE]

Script to run VSPAERO with various options.

options:
  -h, --help            show this help message and exit
  --dryrun, -d          Execute without running VSPAERO
  --cleanup, -c         Remove all files but .lod, .history, and .stab
  --verbose, -v         Increase verbosity
  --resolution {low,medium,high}, -r {low,medium,high}
                        Set resolution of run
  --jobs JOBS, -j JOBS  -omp setting of VSPAERO
  --wake WAKE, -w WAKE  Number of wake iterations
  --force, -f           Re-compute everything
  --ignore FOO,BAR, -i FOO,BAR
                        Cases to skip, comma separated
  --only FOO,BAR, -o FOO,BAR
                        Only run these cases, comma separated
  --runparams RUNPARAMS, -p RUNPARAMS
                        runparams.jsonc file
  --progressfile PROGRESSFILE
```

		
generates .cvs, vspaero files and runs vspaero based on the parameters defined
in `runparams.json` - see included example.

requres vsp python API, see [this
page](https://kontor.ca/post/how-to-compile-openvsp-python-api/) on how to create a venv with VSP api.
run.sh and runstab.sh need to be copied into the working directory for this
script to work.

## vsp2jsbsim.py

```bash
python3 vsp2jsbsim.py --help
usage: vsp2jsbsim.py [-h] [--debug] [-w WAKE_ITERATIONS] [--runparams RUNPARAMS]

Process some integers.

options:
  -h, --help            show this help message and exit
  --debug               Enable debug mode
  -w WAKE_ITERATIONS, --wake_iterations WAKE_ITERATIONS
                        Number of wake iterations
  --runparams RUNPARAMS, -p RUNPARAMS
                        runparams.jsonc file
```

### vsp2jsbsim.py design:

the script performs the following high-level steps in this order:
- read runparams.json
- read .history files and map aerodata to a database named `dataset.json`
- write database to file to allow for manual inspection if needed
- process aerodata in database and write data to JSB functions in output XML
- read stability file from stability analysis
- process stability data and write data to JSB functions in output XML
- assign stability and aerodata to the appropriate axis
- write output XML


## First time setup:
- create .vsp3 model with all necessary control surfaces. The control Surfaces group names should be used as the keys in the `deflection_cases` section of the `runparams.jsonc` file. The arrays should be a list of the deflection angles for each surface deflection case VSP will run.  

```json
	"deflection_cases": {
        "elevators": [1, 4],
        "ailerons": [1, 4],
        "rudder": [1, 4]
    },
```

- Fill out the rest of runparams.json

After this, each time a new version is made of the .vsp3 file, the new tables may be calculated with runvsp.py, then the data extracted with vsp2jsbsim.py.
