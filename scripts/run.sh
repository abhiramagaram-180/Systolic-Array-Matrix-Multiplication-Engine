#!/bin/sh
# Compile and run the simulation (run from the project root)
iverilog -g2001 -o sim.out rtl/*.v tb/tb_top.v && vvp sim.out
