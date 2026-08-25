# Open Nuclear Engineering Teaching Suite 2.0.0

Released 25 August 2026.

Version 2.0.0 is a major desktop-interface and computational-architecture
release. Reactor Physics, Thermal Hydraulics and LOCA, and Core Loading now
launch responsive native PySide6 interfaces with PyQtGraph engineering plots
by default. Fixed-step model integration is separated from throttled display
updates so interactive controls and resizing remain responsive under load.

## Highlights

- Responsive PySide6/PyQtGraph default front ends for all three software-only
  simulators.
- Shared GUI-neutral control backends for Reactor Physics and Thermal
  Hydraulics, preserving fixed numerical timesteps independently of rendering.
- Optional Dear PyGui comparison front ends and retained legacy Tkinter
  interfaces.
- A more tightly converged Core Loading neutronics/thermal/xenon feedback
  iteration, including long depletion-step subdivision and convergence tests.
- Representative SCRAM-only prompt kinetics and independent protection-bank
  worth, with fault-aware behavior and persistent decay heat.
- Expanded regression coverage for model controls, scenarios, responsiveness,
  feedback convergence, and GUI-neutral backends.
- The optional hardware-panel edition now shares the responsive reactor
  frontend and GUI-neutral backend by default; its physical build and firmware
  remain explicitly untested.

The Hardware Reactor Control Panel remains explicitly untested hardware and is
not validated for connection to real equipment. All simulators remain
qualitative classroom tools and are not suitable for design, licensing,
operations, safety analysis, or accident prediction.

The proposed Subchannel Explorer is deferred to a post-2.0 release.
