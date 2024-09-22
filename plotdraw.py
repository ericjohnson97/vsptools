#!/usr/bin/env python3
import json
import matplotlib.pyplot as pyplot
import numpy as np
import argparse
import sys

wake_iterations = 3

def parse_arguments():
    parser = argparse.ArgumentParser(description="Plot data from .history or .lod files.")
    parser.add_argument("input_file", help="Path to the .history or .lod file.")
    parser.add_argument("-x", "--x_axis", default=None, help="X-axis variable (default: AoA for history, yavg for lod).")
    parser.add_argument("-y", "--y_axis", default=None, help="Y-axis variable (default: CL for history, Cl for lod).")
    parser.add_argument("-a", "--aoa", type=float, help="Filter data by Angle of Attack (AoA).")
    parser.add_argument("-m", "--mach", type=float, help="Filter data by Mach number.")
    parser.add_argument("-b", "--beta", type=float, help="Filter data by beta angle.")
    parser.add_argument("-w", "--wing", type=float, help="Filter data by wing (for lod files).")
    parser.add_argument("-hl", "--headless", action="store_true", help="Run in headless mode (no plot display).")
    
    return parser.parse_args()

def initialize_data(data_order):
    return {variable: [] for variable in data_order}

def read_file(args):
    if '.history' in args.input_file:
        data_order = ['Mach','AoA','Beta','CLo','CLi','CLtot','CDo','CDi','CDtot','CDt','CDtot_t',
                      'CSo','CSi','CStot','L/D','E','CFxo','CFyo','CFzo','CFxi','CFyi','CFzi',
                      'CFxtot','CFytot','CFztot','CMxo','CMyo','CMzo','CMxi','CMyi','CMzi',
                      'CMxtot','CMytot','CMztot','T/QS']
        X = args.x_axis or 'AoA'
        Y = args.y_axis or 'CL'
        TYPE = 'history'
    elif '.lod' in args.input_file:
        data_order = ['wing', 'S', 'yavg', 'chord', 'v/vref', 'Cl', 'Cd', 'Cs', 'compname', 'Mach', 
                      'AoA', 'beta', 'Cx', 'Cy', 'Cz', 'CMx', 'CMy', 'CMz']
        X = args.x_axis or 'yavg'
        Y = args.y_axis or 'Cl'
        TYPE = 'lod'
    else:
        print('Incorrect filetype')
        sys.exit(1)

    data = initialize_data(data_order)
    with open(args.input_file) as f:
        input_txt = f.readlines()
    
    return data, data_order, X, Y, TYPE, input_txt

def process_data(data, data_order, input_txt, TYPE):
    db = []
    if TYPE == 'history':
        for i in range(len(input_txt)):
            if input_txt[i].startswith('Solver Case:'):
                l = i + 2 + wake_iterations
                t = input_txt[l].split()[1:]  # Remove the first entry from the array
                # Check if the lengths match
                if len(t) != len(data_order):
                    print(f"Warning: Mismatch between data_order length ({len(data_order)}) and line length ({len(t)})")
                    print(f"Line content: {t}")
                    continue  # Skip this line if lengths don't match

                dataset = {data_order[n]: t[n] for n in range(len(t))}
                db.append(dataset)
    else:
        collect_w = False
        for line in input_txt:
            if line == '\n':
                collect_w = False
            elif collect_w:
                values = line.split()[1:]  # Remove the first entry from the array
                if len(values) != len(data_order):
                    print(f"Warning: Mismatch between data_order length ({len(data_order)}) and line length ({len(values)})")
                    print(f"Line content: {values}")
                    continue  # Skip this line if lengths don't match
                
                dataset = {data_order[n]: values[n] for n in range(len(values))}
                db.append(dataset)
            elif line.startswith('   Wing'):
                collect_w = True
    
    # Populate the data dictionary
    for dataset in db:
        for key in dataset.keys():
            data[key].append(float(dataset[key]))

def format_cases(data, args, TYPE):
    cases = {'AoA': [args.aoa, None], 'Beta': [args.beta, None], 'Mach': [args.mach, None]}
    if TYPE == 'lod':
        cases['wing'] = [args.wing, None]
    
    for c in cases.keys():
        values = set(data[c])
        if cases[c][0] is not None:
            values = {cases[c][0]}
        cases[c][1] = values
    
    return cases

def plotter(data, first_set, second_set, param1, param2, X, Y, HEADLESS):
    for first_val in first_set:
        for second_val in second_set:
            x_values = []
            y_values = []

            for idx in range(len(data[X])):
                two_is_good = data.get(param2, [None])[idx] == second_val or second_set == ['']
                if data[param1][idx] == first_val and two_is_good:
                    x_values.append(data[X][idx])
                    y_values.append(data[Y][idx])

            if x_values and y_values:
                label = f"{param1}={first_val}" + (f" {param2}={second_val}" if len(second_set) > 1 else "")
                pyplot.plot(x_values, y_values, label=label)

                if HEADLESS:
                    print(f"x_values: {x_values}, y_values: {y_values}")

    # Set the title, x-label, and y-label
    pyplot.title(f"{Y} vs {X}")  # Adding a title based on X and Y
    pyplot.xlabel(X)
    pyplot.ylabel(Y)

    # Adjust the legend to be outside the plot on the right
    pyplot.legend(loc='upper right', fontsize='small')

    # Adjust layout to make space for the legend
    pyplot.tight_layout(rect=[0, 0, 0.85, 1])
    
    if not HEADLESS:
        pyplot.show()


def main():
    args = parse_arguments()
    data, data_order, X, Y, TYPE, input_txt = read_file(args)
    process_data(data, data_order, input_txt, TYPE)
    cases = format_cases(data, args, TYPE)
    
    HEADLESS = args.headless
    if X == 'AoA':
        plotter(data, cases['Mach'][1], cases['Beta'][1], 'Mach', 'Beta', X, Y, HEADLESS)
    elif X == 'Mach':
        plotter(data, cases['AoA'][1], cases['Beta'][1], 'AoA', 'Beta', X, Y, HEADLESS)
    elif X == 'Beta':
        plotter(data, cases['AoA'][1], cases['Mach'][1], 'AoA', 'Mach', X, Y, HEADLESS)
    elif TYPE == 'lod':
        plotter(data, cases['wing'][1], [''], 'wing', '', X, Y, HEADLESS)
    
    pyplot.xlabel(X)
    pyplot.ylabel(Y)
    pyplot.legend()
    if not HEADLESS:
        pyplot.show()

if __name__ == "__main__":
    main()
