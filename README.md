### Python toolset to create JSBSim flight dynamics models with VSPAERO
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

## vsp2jsbsim.py design:

the script performs the following high-level steps in this order:
- read runparams.json
- read .history files and map aerodata to a database named `dataset.json`
- write database to file to allow for manual inspection if needed
- process aerodata in database and write data to JSB functions in output XML
- read stability file from stability analysis
- process stability data and write data to JSB functions in output XML
- assign stability and aerodata to the appropriate axis
- write output XML


# First time setup:
- create .vsp3 model with all necessary control surfaces. control surface names should match the names in runparams['files'], except the ones specified in manual_set to be rotated instead of using subsurfaces.
- set up folder structure and create initial .vspaero files (TODO: automate this part step based on runparams.json input)
- write runparams.json

After this, each time a new version is made of the .vsp3 file, the new tables may be calculated with runvsp.py, then the data extracted with vsp2jsbsim.py.
