# BWR critical-power screening method

The axial inspector uses an open critical-quality/boiling-length (X-L)
screening method. This follows the public CISE-family approach of comparing the
local equilibrium quality with a critical quality that depends on pressure,
mass flux, hydraulic diameter, and heated boiling length. Public background and
applicability data are available in IAEA-TECDOC-1203, *Thermohydraulic
relationships for advanced water cooled reactors*, and the open paper
*Critical Power Prediction by Mechanistic Model of Liquid Film Flow* (Journal
of Nuclear Science and Technology 25(12), 1988).

This repository deliberately uses a transparent generic screening form rather
than proprietary fuel-design coefficients:

`xcrit = clamp((0.62 - 0.018(P - 7)) (G/1500)^0.10
(Dh/0.012)^0.15 / (1 + 0.08 Lb), 0.12, 0.78)`

with pressure `P` in MPa, mass flux `G` in kg/m2-s, hydraulic diameter `Dh` in
metres, and boiling length `Lb` in metres. Critical channel power is the power
that raises the channel enthalpy to `hf + xcrit hfg` at the evaluated axial
location. CPR is critical channel power divided by actual channel power.

The result is emitted only where all guards pass: 3-10 MPa, 500-3000 kg/m2-s,
5-20 mm hydraulic diameter, positive boiling length, and equilibrium quality
between -0.05 and 0.80. Outside this envelope CPR is `NaN`, not extrapolated.

Channel pressure is iterated from Darcy friction, distributed spacer loss,
gravity, and acceleration components. User-visible radial, enthalpy-rise, and
local heat-flux factors are declared in `BWRHotChannelGeometry`.

This method is diagnostic. It is not GEXL, a fuel-vendor correlation, a safety
limit MCPR, or a licensing calculation, and it cannot actuate reactor trip or
safety injection.

Sources:

- https://www-pub.iaea.org/MTCD/Publications/PDF/te_1203_prn.pdf
- https://www.jstage.jst.go.jp/article/jnst1964/25/12/25_12_914/_pdf
