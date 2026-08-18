# Physical Mockup Reactor Control Panel — Student Project Guide

> [!CAUTION]
> # THIS SUGGESTED HARDWARE BUILD HAS NOT BEEN TESTED
>
> No physical prototype represented by this guide has been assembled,
> electrically verified, commissioned, calibrated, soak-tested, or validated by
> the project. The bill of materials, wiring, firmware, and procedures are a
> student-project starting point—not an approved design. Independent competent
> review, a documented hazard assessment, current-limited bench testing, and
> completion of every acceptance test are mandatory before demonstration. Never
> connect this mockup to real reactor, laboratory, industrial control,
> protection, or safety-related equipment.

## 1. Project intent and boundary

Build a tabletop operator panel that controls the teaching simulator over an
isolated USB connection. The project combines nuclear-engineering human factors,
instrumentation, embedded programming, fabrication, configuration management,
and verification.

This is an educational mockup only. It must never connect to reactor, laboratory
protection, process-control, or safety-related equipment. Use only SELV power
(5/12 V DC), fused at the supply, with no exposed mains wiring inside the panel.

## 2. Recommended team structure and deliverables

For a society project, use five work packages:

1. **Systems and configuration:** requirements, interface-control document,
   wiring revision control, risk register, and final integration.
2. **Human factors:** panel hierarchy, labeling, control coding, alarm colors,
   reach/visibility review, and operator procedure.
3. **Electrical:** schematics, harness, grounding, fuse, connectors, driver
   boards, continuity tests, and as-built drawings.
4. **Mechanical:** enclosure, front plate, component cut-outs, guards, legends,
   mounting, ventilation, and strain relief.
5. **Software and V&V:** firmware, serial protocol, simulator integration,
   automated tests, test records, fault injection, and release package.

Required final artifacts: requirements specification, block diagram, schematic,
bill of materials, pin list, panel drawing, source code, compiled firmware
version, calibration record, test plan/results, operator manual, maintenance
manual, hazard review, and a demonstration video.

## 3. Reference architecture

```text
5 V controls/sensors ─┐
                      ├─ Arduino Mega ── isolated USB ── Windows PC
12 V lamps ─ drivers ─┘       │                         simulator GUI
                              └─ link watchdog
```

The PC remains authoritative for physics. The microcontroller scans controls,
debounces discrete inputs, scales analog inputs, and drives indications received
from the PC. It must not calculate reactor physics.

## 4. Baseline bill of materials

Quantities are a starting point; choose reputable, locally supported parts.

| Item | Qty | Specification / purpose |
| --- | ---: | --- |
| Arduino Mega 2560 or compatible | 1 | Sufficient analog and digital I/O |
| USB isolator (full-speed) | 1 | Separates PC ground from panel prototype |
| Regulated enclosed 12 V DC supply | 1 | Certified external brick, 2–3 A |
| 12-to-5 V buck converter | 1 | Logic supply, ≥1 A, fused |
| Panel fuse and holder | 1 | Sized after measured load; start evaluation at 1 A |
| Latching red mushroom button | 1 | SCRAM mockup; guarded/recessed reset separately |
| Momentary pushbuttons | 6 | Start, pause, reset, step, trim ± |
| Three-position maintained selector | 1 | Manual / auto / load follow |
| 10 kΩ linear panel potentiometers | 6 | Analog controls; use quality multi-turn units where useful |
| 12 V LED indicators | 5 | High power, high temperature, low flow, trip, link |
| ULN2803A driver module or MOSFET board | 1 | Lamp loads; do not source lamps from MCU pins |
| Screw terminals / pluggable connectors | as needed | Serviceable harness termination |
| Shielded USB cable with strain relief | 1 | Data link |
| Enclosure/front plate | 1 | Nonconductive prototype or bonded metal enclosure |
| Wire, ferrules, labels, heat-shrink | as needed | Use distinct colors and numbered conductors |

Optional phase-two items include stepper-driven analog meters, a small status
display, rotary encoders, audible annunciator, key switch, and instructor fault
panel. Add these only after the baseline passes acceptance tests.

## 5. Baseline control allocation

The supplied firmware targets an Arduino Mega:

| Function | MCU pin | Field device |
| --- | ---: | --- |
| Rod insertion (0% withdrawn, 100% inserted) | A0 | 10 kΩ linear potentiometer |
| Coolant flow | A1 | 10 kΩ linear potentiometer |
| Heat sink/load | A2 | 10 kΩ linear potentiometer |
| Power setpoint | A3 | 10 kΩ linear potentiometer |
| Boron equivalent | A4 | 10 kΩ linear potentiometer |
| Fault severity | A5 | 10 kΩ linear potentiometer |
| Start / Pause / SCRAM / Reset | D22–D25 | Dry contact to logic ground |
| Step / Trim − / Trim + | D26–D28 | Dry contact to logic ground |
| Manual / Auto / Load follow | D29–D31 | Selector contacts to logic ground |
| High power / high temp / low flow / trip | D40–D43 | Driver inputs |
| Link healthy | D44 | Driver input |

Each potentiometer connects between regulated 5 V and logic ground, with the
wiper connected to its analog pin. Add a 1 kΩ series resistor at each wiper and
a 100 nF capacitor from the analog pin to ground close to the controller. Do not
apply 12 V to any MCU input.

Buttons use `INPUT_PULLUP`: open reads high and a pressed contact to ground reads
low. Install a 100 nF capacitor across noisy contacts only after confirming that
it does not create undesirable edge delays. The firmware also applies 35 ms
debouncing.

For 12 V lamps, connect each lamp between fused +12 V and a low-side driver
output. Connect the driver input to D40–D44 and the driver logic ground to panel
logic ground. If using discrete MOSFETs, specify logic-level devices, gate
resistors and pull-downs; add flyback diodes for inductive loads. LEDs are not
inductive.

## 6. Panel layout and human factors

Divide the face into clear functional zones:

- **Reactivity control:** rod position, boron equivalent, trim, control mode.
- **Heat removal:** coolant flow and heat-sink/load.
- **Run control:** start, pause, step, and guarded reset.
- **Protection:** prominent red mushroom SCRAM and trip annunciator.
- **Status:** high power, high temperature, low flow, and communications link.

Place SCRAM where it can be struck quickly but not accidentally brushed. Give it
a distinctive shape and red color; do not rely on color alone. Label every
control with name, units, direction, and range. Use clockwise/upward motion for
increasing values consistently. Keep fault severity on an instructor-only area.
Conduct a paper/full-size cardboard layout review before cutting the front plate.

## 7. Electrical and mechanical build sequence

1. Freeze requirements and issue interface-control document revision 1.
2. Make a full-scale paper layout; perform reach, label, and ambiguity review.
3. Draw the schematic and pin-to-wire schedule before fabrication.
4. Bench-test the MCU, one button, one potentiometer, and one lamp driver.
5. Fabricate the front plate; deburr holes and fit guards/legends.
6. Mount low-voltage power, fuse, controller, drivers, and terminal blocks on a
   removable back plate. Separate power wiring from analog signal wiring.
7. Build labeled harnesses with ferrules and service loops. Provide USB and DC
   strain relief. Never use solder alone as mechanical support.
8. With power disconnected, perform point-to-point continuity and unintended
   short tests against the schematic. Independently inspect polarity.
9. Power from a current-limited bench supply first. Verify 12 V and 5 V rails
   before fitting the MCU and connecting the PC.
10. Record the as-built schematic, wire list, photographs, and serial numbers.

## 8. Software installation

On the PC, install the base project and `pyserial`:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r simulators/HardwareReactorControlPanel/requirements-hardware.txt
python -m unittest discover -s simulators/HardwareReactorControlPanel -p "test_*.py"
```

Open `firmware/reference_panel/reference_panel.ino` in Arduino IDE, select
**Arduino Mega or Mega 2560**, select the correct port, compile, and upload.
Record the Git commit and firmware build date on the test sheet.

Find the Windows port in Device Manager, then run:

```powershell
python simulators/HardwareReactorControlPanel/main.py --port COM5
```

For GUI work without hardware, use `--no-hardware`. Do not edit the canonical
reactor simulator to change pin mappings; change only the hardware-edition
firmware/protocol under configuration control.

## 9. Calibration

For every analog control:

1. Mark the mechanical minimum, midpoint, and maximum.
2. Read at least 20 serial samples at each point and record raw ADC mean/range.
3. Confirm the simulator reaches its intended software range.
4. Check monotonicity at 10% increments; no reversal or discontinuity is allowed.
5. If end tolerances are excessive, implement per-channel calibration constants
   in firmware and repeat the test.
6. Apply a label with calibration date and firmware revision.

The current reference maps ADC 0–1023 linearly. Potentiometer tolerance and
mechanical end stops mean measured calibration is essential.

## 10. Commissioning and acceptance tests

Execute and sign the following with two students: one operator and one witness.

| ID | Test | Acceptance criterion |
| --- | --- | --- |
| SW-01 | Protocol unit tests | All pass |
| EL-01 | Power-off continuity | Matches schematic; no shorts |
| EL-02 | Rail test | Rails within component limits and correct polarity |
| IO-01 | Each button 50 operations | Exactly one command per press; no missed press |
| IO-02 | Each analog full travel | Correct direction/range; stable within agreed tolerance |
| IO-03 | Mode selector | Exactly one valid mode at each detent |
| IO-04 | Each lamp command | Correct labeled lamp, no cross-lighting |
| IF-01 | Disconnect USB while running | GUI continues; link lamp clears within 2 s |
| IF-02 | Reconnect USB | Restart application restores communication cleanly |
| IF-03 | Malformed/out-of-range input | Rejected or clamped; simulator remains responsive |
| HF-01 | Blind control identification | Operators identify controls by label/shape without ambiguity |
| SYS-01 | Start-to-SCRAM scenario | SCRAM activates trip state and rods respond as GUI design intends |
| SYS-02 | 30-minute soak | No reset, queue growth, stuck input, or excessive heating |

Capture test date, hardware revision, firmware commit, software commit, PC,
operator, witness, measured result, pass/fail, and corrective-action reference.

## 11. Failure behavior and limitations

- The protocol accepts only allow-listed commands and clamps analog ranges.
- Sequence numbers suppress repeated/out-of-order commands during a session.
- Serial messages are bounded to 1024 bytes and queues are bounded.
- If PC state is absent for two seconds, reference firmware extinguishes all
  lamps including the link lamp. This means **dark lamps cannot be interpreted
  as a safe plant state**; operators must check link status.
- Losing the panel does not stop the teaching model. This preserves classroom
  continuity, but is not behavior suitable for a real control/protection system.
- Closing/reopening the serial device currently requires restarting the hardware
  application. Automatic reconnection is a suitable advanced student task.

## 12. Suggested advanced project backlog

After baseline acceptance, student teams can add: configuration-file pin maps;
CRC-framed binary protocol comparison; automatic reconnect; heartbeat and panel
self-test; input ownership arbitration between GUI and panel; calibration stored
in EEPROM; output meter drivers; annunciator acknowledge/test; recorded hardware
event logs; a loopback simulator; hardware-in-the-loop CI fixture; accessibility
review; enclosure EMC testing; and a formal FMEA.

Each enhancement must introduce requirements and tests before implementation.
Physics-model changes remain outside this hardware project unless separately
reviewed and revalidated.
