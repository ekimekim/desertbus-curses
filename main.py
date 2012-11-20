#!/usr/bin/python

import curses
import math
from curses.wrapper import wrapper as curses_wrapper
import sys
from itertools import count
import time
import random

# --- CONFIG ---

ANGLE_DELTA = math.pi / 20 # Bus direction modifier in radians when steering
ANGLE_LEAN = math.pi / 200 # Bus direction modifier in radians on every tick (to the right).
SPEED_DELTA = 0.01 # Bus speed change in pixels/tick/tick when accelerating/breaking.
SPEED_MAX = 2 # Max speed in pixels/tick
SPEED_OVERREACH = 0.2 # This is how far above max speed the internal speed counter can reach (without actually being faster), this is a hack to offset the problem with needing to stop accelerating to steer.
SPEED_DRAG = 0.005 # Bus speed decrease in pixels/tick/tick on every tick. Should be < SPEED_DELTA
SPEED_DRAG_OFFROAD = 0.05 # Bus speed decrease in pixels/tick/tick on every tick while offroad. Should be > SPEED_DELTA
ROAD_WIDTH = 20 # Road width in pixels. Must be even.
TICK_INTERVAL = 0.05 # Minimum tick interval in seconds 
TRIP_LENGTH = 1152000 # Distance from Tuscon to Las Vegas in pixels. Formula is (trip time in secs * SPEED_MAX / TICK_INTERVAL)
SPEED_MAX_MPH = 45 # Max speed in miles per hour. Used to get miles-pixels conversion for display.
BKGD_CHARS = "  .," # Charset to randomise background from. The same character many times increases its chance.
CRASH_DELAY = 5 # Delay before reset on crash

# Bus ascii art. All lines MUST be equal width.
BUS_ART = "**" "\n" \
          "!!" "\n" \
          "!!"

# --- END CONFIG ---

# Important note about arrow keys: Limitations in curses mean I can only catch each keypress.
# This means that holding it down only produces keystrokes every so often
# On my machine, and I believe typically, this isn't a problem since we get at least one
# every TICK_INTERVAL. But it may become a problem at small TICK_INTERVALs.

def scr_mid(scr):
	y, x = scr.getmaxyx()
	return (y/2, x/2)


def intro():
	print "Hello, and welcome to Desert Bus: Curses Edition!\n" \
	      "All the extended gameplay of the Desert Bus you love, in a convenient " \
	      "terminal-friendly format!\n" \
	      "However, an important note. There are some issues with how curses " \
	      "handles keyboard input. Pressing a button only sends a single keystroke at first, " \
	      "it will send many keystrokes after holding it a little while.\n" \
	      "Also, if you press two buttons at once (say, steer while accelerating), " \
	      "it will think you released the first button.\n" \
	      "Ok, good luck! Up/down to acclerate/brake, left/right to steer.\nPress enter to start."
	raw_input()

intro()


# NOTE: curses_wrapper calls main() immediately. Yeah, it's bussing retarded.
@curses_wrapper
def main(stdscr):

	score_points = 0
	score_crash = 0

	curses.curs_set(0) # Turn visible cursor off
	stdscr.nodelay(1) # Non-blocking input

	BUS_WIDTH = len(BUS_ART.split('\n')[0])
	MILES_PER_PIXEL = SPEED_MAX_MPH / 3600.0 * TICK_INTERVAL / SPEED_MAX
	runtime_start = time.time()

	while 1:
		vel_speed = 0 # velocity magnitude
		vel_angle = 0 # velocity angle in radians. 0 is forward, road-wise.
		bus_x = 0 # 0 is middle of road
		bus_y = 0 # 0 is start of trip

		while 1:
			angle_dir = 0
			speed_dir = 0
			tick_start = time.time()

			while 1:
				key = stdscr.getch()
				if key == ord('q'):
					return 0
				elif key in (curses.KEY_LEFT, curses.KEY_RIGHT):
					angle_dir = -1 if key == curses.KEY_LEFT else 1
				elif key in (curses.KEY_UP, curses.KEY_DOWN):
					speed_dir = -1 if key == curses.KEY_DOWN else 1
				elif key == -1:
					# No input remaining
					break

			# Update vel based on input
			vel_angle = ANGLE_DELTA * angle_dir
			vel_speed += SPEED_DELTA * speed_dir
			if vel_speed > SPEED_MAX+SPEED_OVERREACH: vel_speed = SPEED_MAX+SPEED_OVERREACH
			if vel_speed < 0: vel_speed = 0

			# Bus drag and lean
			if not -ROAD_WIDTH/2 <= bus_x - 1 <= ROAD_WIDTH/2 - BUS_WIDTH + 1:
				# Bus is OFFROAD!
				vel_speed -= SPEED_DRAG_OFFROAD
				if vel_speed < 0:
					# CRASHED!
					stdscr.move(3, scr_mid(stdscr)[1]-4)
					stdscr.addstr(" CRASHED! ")
					stdscr.refresh()
					time.sleep(CRASH_DELAY)
					score_crash += 1
					break
			else:
				vel_speed -= SPEED_DRAG
				if vel_speed < 0: vel_speed = 0
			vel_angle += ANGLE_LEAN

			# Bus position move
			vel_real_speed = min(vel_speed, SPEED_MAX)
			bus_x += math.sin(vel_angle) * vel_real_speed
			bus_y += math.cos(vel_angle) * vel_real_speed

			# Check for dest reached
			if bus_y >= TRIP_LENGTH:
				# TODO win
				raise Exception('Bus reached finish!')

			# Draw background
			stdscr.move(0,0)
			for y in range(stdscr.getmaxyx()[0]):
				# A short explanation. We seed an RNG from the program start time (hence unique per invocation)
				# and y-bus_y. The idea is that the terrain moves down the screen as bus_y increases.
				random.seed((runtime_start, y-int(bus_y)))
				for x in range(stdscr.getmaxyx()[1]):
					if (y+1,x+1) == stdscr.getmaxyx(): break
					stdscr.addch(random.choice(BKGD_CHARS))

			# Draw road
			for y in range(stdscr.getmaxyx()[0]):
				stdscr.move(y, scr_mid(stdscr)[1] - ROAD_WIDTH/2)
				stdscr.addstr('#' + ' ' * ROAD_WIDTH + '#')

			# Draw bus
			for y, line in zip(count(scr_mid(stdscr)[0]), BUS_ART.split('\n')):
				stdscr.move(y, int(scr_mid(stdscr)[1] + bus_x))
				stdscr.addstr(line)

			# Draw stats
			stdscr.move(1,0)
			stdscr.addstr(" Score: %d:%d " % (score_points, score_crash))
			stdscr.move(2,0)
			speed_miles = vel_real_speed * (float(SPEED_MAX_MPH) / SPEED_MAX)
			stdscr.addstr(" Speed: %.2fmph " % speed_miles)
			stdscr.move(3,0)
			odo_miles = bus_y * MILES_PER_PIXEL
			stdscr.addstr(" Odometer: %.2fmi " % odo_miles)

			# Write to screen
			stdscr.refresh()

			# Wait to end of tick
			tick_end = time.time()
			# NOTE: This isn't monotonic so will break if you change system time
			tick_so_far = tick_end - tick_start
			if tick_so_far < TICK_INTERVAL:
				time.sleep(TICK_INTERVAL - tick_so_far)
