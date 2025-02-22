### Python toolset to create JSBSim flight dynamics models with VSPAERO

Special thanks to Jüttner Domokos for publishing his work. This repository is a fork of his original work, which can be found [here](https://github.com/Rudolf339/vsptools). I have decided to build on his work and add more features that are relevant to me. I have a desire to be able to take an OpenVSP model and generate aerodynamics data for JSBSim. I have special interest in generating my JSBsim models to be compatible with both ardupilot and PX4. 

This project is a work in progress and does not work yet, but I am looking forward to working on this more in the coming months.

## Author: Jüttner Domokos
## Licence: GPLv2

# plotdraw.py
Generate a plot of the VSP .history output
usage:
`$ python3 plotdraw.py path/to/vsp.history {options}`

options:
	-x
		value may be `AoA`, `Mach`, `beta`
		defaults to AoA
	-y
	    value may be `Mach`, `AoA`, `beta`, `CL`, `CDo`, `CDi`, `CDtot`, `CS`,
		`L/D`, `E`, `CFx`, `CFz`, `CFy`, `CMx`, `CMz`, `CMy`, `T/QS`
		defaults to CL

# runvsp.py
options:

	-jn
		n is the number of threads passed to vspaero with the -omp setting

	-wn
		n is the number of wake iterations, defaults to 3
		
	-d
		dryrun, all files are generated but vspaero isn't executed
	-h 
		high-res run
	-m
		medium-res run
	-c
		cleanup, removes files that are later not used. Can save large amounts
		of storage, .adb files in particular can make up ~90% of the used
		space
		
	-v
		verbose, also writes out .vsp3 for every case
	--progressfile=progressfile.json
		continue from where last session was interrupted
		
generates .cvs, vspaero files and runs vspaero based on the parameters defined
in `runparams.json` - see included example.

requres vsp python API, see [this
page](https://kontor.ca/post/how-to-compile-openvsp-python-api/) on how to create a venv with VSP api.
run.sh and runstab.sh need to be copied into the working directory for this
script to work.

# vsp2jsbsim.py
options:

	-wn
		n is number of wake iterations, defaults to 3
		
	--debug
		enables a few extra print statements, nothing that particularly
		benefits the user, used for development
		
extracts the data from the .history files and formats them into jsbsim tables.
Takes the same runparams.json as input

It does not create the <axis> definitions, those need to be done manually

# First time setup:
- create .vsp3 model with all necessary control surfaces. control surface names should match the names in runparams['files'], except the ones specified in manual_set to be rotated instead of using subsurfaces.
- set up folder structure and create initial .vspaero files (TODO: automate this part step based on runparams.json input)
- write runparams.json

After this, each time a new version is made of the .vsp3 file, the new tables may be calculated with runvsp.py, then the data extracted with vsp2jsbsim.py.
