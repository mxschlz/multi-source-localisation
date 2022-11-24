import adstfunc as func
import slab
from pathlib import Path
import os
import freefield


# initialization + checking for existing ID
id = func.randId()

#print(id)  # for debugging

trials = input("Pls enter Value for Amount of trials, press enter for default\n")

if trials == "":
    trials = 50
else:
    # failsafe
    try:
        int(trials)
    except:
        print("your input is invalid pls enter an numeric value")
        exit(1)

print(trials)  #for debugging

#TODO
# load sound files
gender = "M"  # F or M
talker = "max"  # number of talker
root = Path("D:/Projects/multi-source-localisation/data/")
duration = 2.0
samplerate = 48828
for number in list(range(1, 2)):
    filename = Path(f"talker-{talker}_number-{number}_gender-{gender}.wav")
    filepath = Path(root/f"{talker}")
    input(f"Press any key to start recording number {number}")
    sound = slab.Sound.record(duration=duration, samplerate=samplerate)
    if not os.path.exists(filepath):
        os.mkdir(filepath)
    sound.write(filepath/filename)
    print(f"Sucessfully saved sound {number} from talker {talker}!")
# 1. locate sound files
# 2. load sound files


#TODO
# test for loudness threshold and write a quick savefile
noise = slab.Sound.pinknoise(duration=2.0)
tone = slab.Sound.tone(duration=2.0)
stairs = slab.Staircase(start_val=70, n_reversals=5, step_sizes=[4, 1])
freefield.initialize(setup="dome", device=["RX810", "RX8", "E:/projects/multi-source-localization/data/play_buf_msl.rcx"])
speakers = list(x for x in range(20, 27) if x is not 23)
for level in stairs:
    tone.level = level
    combined = tone + noise
    combined.play()
    with slab.key("Please press button between 1 and 5.") as key:
        response = key.getch()
    if response == 121:
        stairs.add_response()
    elif response == 110:
        stairs.add_response(False)


# 1. checking if loudness test is needed + setting boolean
# 2. set up adaptive staircase
# 3. running the test
# 4. writing savefile and closing it afterwards

#TODO
# generating a masker noise
# setting up a staircase for level manipulation


#TODO
# setting up the actual trial


# Task: find the loudness threshold of a noise that masks the content of a speech sound
# Use an "adaptive staircase" method from slab to find this loudness threshold for every participant
# generate a unique participant ID DONE
# load sound files of speech sounds (talker counting from 1-10)
# generate a masker noise
# set up an adaptive staircase that changes the level of the masker on each step
# each round of the staircase should play a random speech sound and the masker at the same time
# ask for participant to indicate which number they have heard
# check if participant response was correct
# save data once the threshold is reached (don't forget to add participant ID)
# extra 1: rove the loudness of both the talker and the masker
# extra 2: extend the above for speech sounds of multiple talkers
# extra 3: vocode the speech sounds and use those as maskers
