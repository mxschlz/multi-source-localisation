import string
import random
import os


def randId():
    first = input("enter if the participant is visiting for the first time.\n")
    if first.__contains__("y"):
        print("understood yes")
        # generating new participant id
        id = ''.join([random.choice(string.ascii_uppercase + string.digits) for n in range(6)])

        return id

    elif first.__contains__("n"):
        print("understood no\npls enter the id manually")
        id = input("What is the id?\n")
        return id
        #asking for manuell imput, maybe setting up a file system for automatic load/read
    else:
        print("input is invalid, pls answer with either yes or no")
        exit(1)

# creation of a file at the same location
def init(projectName):
    os.mkdir(os.getcwd()+"/"+projectName)
    os.chdir(os.getcwd()+"/"+projectName)
    mastersheat = open("Mastersheet.txt", "x")
    timesheat = open("timesheet.txt", "x")
    print("set up finished")
