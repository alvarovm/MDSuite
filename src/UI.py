"""
Author: Samuel Tovey
Affiliation: Institute for Computational Physics, University of Stuttgart
Contact: stovey@icp.uni-stuttgart.de ; tovey.samuel@gmail.com
Purpose: Functions for the user interface of the LAMMPS analysis suite
"""

import argparse as ap
import os
import numpy
import subprocess as sp
import glob
import shutil
from Classes import Trajectory


def Begin_Program():
    """ Process to begin the program

    The first thing user will see when the run the main.py script, including the flags which should
    be included with it. The function will then process the input including performing a file check before
    returning the data required to build the class to follow.
    """

    def Parser_Function():
        """ Function to collect cmd line arguments"""
        parser = ap.ArgumentParser(description="A post-processing suite for the LAMMPS simulation package")
        parser.add_argument('-n', '--new_project', type=bool, required=False, default=False, help="True/False parameter"
                                                                                                 "to request a new "
                                                                                                 "analysis project")
        parser.add_argument('-p', '--old_project', type=bool, required=False, default=False, help="True/False parameter"
                                                                                                  "to request an old "
                                                                                                  "analysis project "
                                                                                                  "be analyzed again")
        parser.add_argument('-t', '--project_name', type=str, required=True, help="Name of the project, old or new, "
                                                                                  "being analyzed in this run")
        return parser.parse_args()

    def Process_Arguments():
        """ Process the command line arguments """

        args = Parser_Function()

        new_project = args.new_project
        old_project = args.old_project
        project_name = args.project_name

        if new_project == True:
            Check_Directories(project_name)

        elif old_project == True:
            Load_Class(project_name)

        else:
            print("\n --- Error in file input, nothing to study --- \n")

    Process_Arguments()

def Build_Class(project_name: str):
    """ Function to build the class

    args:
        project_name (str) -- Name of the project
    """

    temperature = int(input(" What is the temperature of the system? \n"))
    file = input("Enter a filepath to the input file: \n")

    trajectory_class = Trajectory(file, project_name, temperature)
    print("\n Building database now, this will take some time \n")
    trajectory_class.Build_Database()

    return trajectory_class

def Load_Class(project_name):
    """ Load a pre-existing project

    args:
        project_name (str) -- Name of the project
    """
    print("Not there yet")

def Check_Directories(project_name):
    """ Check for project directory

    Before running a full analysis of the system and loading new data check to see if there is already a directory
    for this project name and ask if it should be used.

    args:
        project_name (str) -- Name of the analysis project
    """

    directories_full = glob.glob("../Project_Directories/*/")
    directories = []  # Define empty array

    for i in range(len(directories_full)):
        directories.append(directories_full[i][23:-1])

    def Get_Input(overwrite_decision=None):
        """ Get the user input

        returns:
            overwrite_decision (str) -- Numeric choice about what to do with previously existing data
        """

        if project_name in directories:
            overwrite_decision = input("\n Project Directory {0} currently exists, please select and option from the "
                                       "following: \n"
                                       "\n   [1] Use data from this directory"
                                       "\n   [2] Overwrite data in this directory"
                                       "\n   [3] Rename this project\n\n".format(project_name))

        return overwrite_decision

    def Process_Decision(decision, project_name):
        """ Process and implement the decision

        args:
            decision (str) -- Numeric decision made
            project_name (str) -- Name of project (Find out why this did not work without explicit declaration)
        """
        if decision == "1":
            Load_Class(project_name)

        elif decision == "2":
            shutil.rmtree("../Project_Directories/{0}".format(project_name))
            Build_Class(project_name)

        elif decision == "3":
            project_name = input("Enter the new project name:  \n")
            Build_Class(project_name)

        else:
            print("\n Option is not recognized - Closing until you have made a decision \n")

    Process_Decision(Get_Input(), project_name)
