OPEN NUCLEAR ENGINEERING TEACHING SUITE 2.1.0
Windows faster-starting folder release

Each simulator has its own folder. Open the appropriate folder and run:

  Reactor-Physics-and-Kinetics-Simulator\
    Reactor-Physics-and-Kinetics-Simulator.exe

  Thermal-Hydraulics-and-LOCA-Simulator\
    Thermal-Hydraulics-and-LOCA-Simulator.exe

  Subchannel-Thermal-Hydraulics-Laboratory\
    Subchannel-Thermal-Hydraulics-Laboratory.exe

  Core-Loading-Simulator\
    Core-Loading-Simulator.exe

  Hardware-Reactor-Control-Panel-UNTESTED\
    Hardware-Reactor-Control-Panel-UNTESTED.exe

WARNING - UNTESTED HARDWARE PROTOTYPE
The suggested physical panel, wiring, and reference firmware have not been
assembled, commissioned, or tested by this project. Never connect them to real
reactor, laboratory, process-control, protection, or safety equipment.

Keep each EXE together with its adjacent _internal folder. The applications
will not run if an EXE is copied out by itself. Python is not required.

This folder-based edition starts faster than the single-file edition because
it does not unpack its bundled Python runtime and libraries at every launch.

The three software-only simulators use responsive native Qt controls and
GPU-accelerated engineering plots by default. Their computational models run
at fixed numerical timesteps independently of display refreshes.

Windows SmartScreen may warn about downloaded, unsigned executables. If you
obtained this release from the official project source, use "More info" and
"Run anyway" after verifying the SHA-256 values in SHA256SUMS.txt.

These are simplified teaching models only. They are not suitable for reactor
design, licensing, safety analysis, operator training, accident prediction,
or real plant operation.

The Reactor Physics and Kinetics Simulator uses validated classroom defaults
at startup. Its instructor panel provides bounded alternative teaching
timescales and an optional advanced core-physics profile, displays any active
model settings, and records them in CSV exports.

License and citation details are included alongside the application folders.
