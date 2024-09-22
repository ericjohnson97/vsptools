#!/usr/bin/env python3
import matplotlib.pyplot as pyplot
import json
import argparse

wake_iterations = 3

def parse_arguments():
    parser = argparse.ArgumentParser(description="Plot data from .lod files.")
    parser.add_argument("input_file", help="Path to the .lod file.")
    parser.add_argument("-x", "--x_axis", default="yavg", help="X-axis variable (default: yavg).")
    parser.add_argument("-y", "--y_axis", default="Cl", help="Y-axis variable (default: Cl).")
    parser.add_argument("-a", "--aoa", default=None, help="Comma-separated list of AoA values to filter.")
    parser.add_argument("-m", "--mach", default=None, help="Comma-separated list of Mach numbers to filter.")
    parser.add_argument("-b", "--beta", default=None, help="Comma-separated list of beta values to filter.")
    parser.add_argument("-w", "--wing", default=None, help="Comma-separated list of wing numbers to filter.")
    
    return parser.parse_args()

def initialize_data():
    data_order = ['wing', 'S', 'yavg', 'chord', 'v/vref', 'Cl', 'Cd', 'Cs',
                  'Cx', 'Cy', 'Cz', 'CMx', 'CMy', 'CMz']
    data_order_2 = ['comp', 'compname', 'Mach', 'AoA', 'beta', 'CL',
                    'CDi', 'CS', 'CFx', 'CFy', 'CFz', 'Cmx', 'Cmy', 'Cmz']
    
    data = {key: [] for key in data_order}
    data_comp = {key: {} for key in data_order_2}
    
    return data, data_comp, data_order, data_order_2

def getdata(line):
    line = ' '.join(line.split())  # Removes redundant spaces
    return [float(val) if val.replace('.', '', 1).isdigit() else val for val in line.split(' ') if val]

def process_file(input_txt, data_order, data_order_2):
    collect_w = False
    collect_c = False
    db = []
    db_comp = []
    db_temp = []
    db_comp_temp = []

    for line in input_txt:
        if line.strip() == '':
            collect_w = False
            collect_c = False
            if db_temp:
                db.append(db_temp)
            if db_comp_temp:
                db_comp.append(db_comp_temp)
            db_temp = []
            db_comp_temp = []
        elif collect_w:
            dataset = {data_order[n]: getdata(line)[n] for n in range(len(getdata(line)))}
            db_temp.append(dataset)
        elif collect_c:
            dataset = {data_order_2[n]: getdata(line)[n] for n in range(len(getdata(line)))}
            db_comp_temp.append(dataset)
        elif line.startswith('   Wing'):
            collect_w = True
        elif line.startswith('Comp'):
            collect_c = True

    return db, db_comp

def filter_data(db, db_comp, AOA, MACH, BETA, WING, X, Y):
    yres = {}
    xres = {}
    yall = []
    xall = []

    for i in range(len(db)):
        aoa = float(db_comp[i][0]['AoA'])
        beta = float(db_comp[i][0]['beta'])
        mach = float(db_comp[i][0]['Mach'])
        
        if (aoa in AOA or None in AOA) and (beta in BETA or None in BETA) and (mach in MACH or None in MACH):
            for d in db[i]:
                if int(d['wing']) in WING or None in WING:
                    wing_index = d['wing']
                    yres.setdefault(wing_index, []).append(float(d[Y]))
                    xres.setdefault(wing_index, []).append(float(d[X]))
                    yall.append(float(d[Y]))
                    xall.append(float(d[X]))
                    
                    txt = f"AoA={aoa} beta={beta} Mach={mach} wing={wing_index}"
                    pyplot.plot(xres[wing_index], yres[wing_index], label=txt)
    
    return xall, yall

def main():
    args = parse_arguments()

    # Initialize data and data_order lists
    data, data_comp, data_order, data_order_2 = initialize_data()
    
    # Parse user-provided filters
    AOA = list(map(float, args.aoa.split(','))) if args.aoa else [None]
    MACH = list(map(float, args.mach.split(','))) if args.mach else [None]
    BETA = list(map(float, args.beta.split(','))) if args.beta else [None]
    WING = list(map(int, args.wing.split(','))) if args.wing else [None]
    
    # Read the input file
    with open(args.input_file, 'r') as f:
        input_txt = f.readlines()
    
    # Process the file
    db, db_comp = process_file(input_txt, data_order, data_order_2)
    
    # Save to debug.json for debugging purposes
    with open('./debug.json', 'w+') as jf:
        json.dump(db, jf, sort_keys=True, indent=4)
    
    # Plotting filtered data
    xall, yall = filter_data(db, db_comp, AOA, MACH, BETA, WING, args.x_axis, args.y_axis)
    
    # Configure the plot
    pyplot.xlabel(args.x_axis)
    pyplot.ylabel(args.y_axis)
    pyplot.title(f"{args.y_axis} vs {args.x_axis}")
    pyplot.legend(loc='center left', bbox_to_anchor=(1, 0.5), fontsize='small')
    pyplot.tight_layout(rect=[0, 0, 0.85, 1])
    pyplot.show()

if __name__ == "__main__":
    main()
