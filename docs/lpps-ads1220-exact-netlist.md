# LPPS + ADS1220IRVAR exact schematic

This document is the electrical source of truth for the LPPS ADC PCB using the
ADS1220IRVAR (RVA, 16-pin VQFN). It describes the R7/R10 DNP assembly option.
The PCB netlist is known; the bare SK8707-01 sensor bridge mapping remains a
working hypothesis until verified by resistance measurements or the topology
scan described below.

## Parts

| Ref | Value / part | Assembly |
|---|---|---|
| U1 | ADS1220IRVAR | Fit |
| J1 | 1x6 host connector | Fit |
| J6 | 1x6 LPPS connector | Fit |
| R1 | 47 ohm, MISO series | Fit |
| R2 | 47 ohm, MOSI series | Fit |
| R3 | 47 ohm, SCLK series | Fit |
| R5 | 2.4 kohm, REFP0-to-VCM | Fit |
| R6 | 2.4 kohm, VCM-to-REFN0 | Fit |
| R7 | 0 ohm, AIN0-to-VCM option | DNP |
| R8 | 0 ohm, AIN1-to-VCM | Fit for the current normal-firmware hypothesis; DNP for topology discovery |
| R9 | 0 ohm, AIN2-to-VCM | Fit for the current normal-firmware hypothesis; DNP for topology discovery |
| R10 | 0 ohm, AIN3-to-VCM option | DNP |
| R11 | 0 ohm, REFN0-to-GND | Fit |
| C1 | 100 nF, DVDD bypass | Fit close to U1 pins 11/2 |
| C2 | 100 nF, AVDD bypass | Fit close to U1 pins 10/3 |
| C3 | 1 uF, optional local bulk bypass | DNP / optional; not present in the current EasyEDA schematic |

## Nets

| Net | Connected pins |
|---|---|
| VCC_3V3 | J1.2, U1.10 AVDD, U1.11 DVDD, C1.1, C2.1 |
| GND | J1.1, U1.1 CLK, U1.2 DGND, U1.3 AVSS, U1.16 CS, R11.2, C1.2, C2.2 |
| SCLK_HOST | J1.3, R3.1 |
| SCLK_ADC | R3.2, U1.15 SCLK |
| DRDY | J1.4, U1.12 DRDY |
| MISO_HOST | J1.5, R1.1 |
| DOUT_ADC | R1.2, U1.13 DOUT/DRDY |
| MOSI_HOST | J1.6, R2.1 |
| DIN_ADC | R2.2, U1.14 DIN |
| REFP0 | U1.7 REFP0, J6.2, R5.1 |
| REFN0 | U1.6 REFN0, J6.1, R6.2, R11.1 |
| VCM | R5.2, R6.1, R7.2, R8.2, R9.2, R10.2 |
| Y_SIG | U1.9 AIN0, R7.1 (DNP), J6.3, J6.4 |
| VCM_Y | U1.8 AIN1, R8.1 |
| VCM_X | U1.5 AIN2, R9.1 |
| X_SIG | U1.4 AIN3/REFN1, R10.1 (DNP), J6.5, J6.6 |

R7 and R10 are physically present as footprints only. Because they are DNP,
`Y_SIG` and `X_SIG` are not electrically connected to `VCM`.

## LPPS internal connections (working hypothesis)

The following mapping comes from the traced internal diagram supplied for this
sensor. It is not documented in the public SK8707-01 data sheet, and badjeff has
confirmed that he does not know how the SK8707-01 sensor board is routed.
The public SK8707-01 PDF describes the controller-equipped PS/2 module pinout
only; it does not document the raw six-wire strain-gauge sensor pinout.

| Element | LPPS terminals |
|---|---|
| UP gauge | J6.3 - J6.2 |
| DOWN gauge | J6.4 - J6.1 |
| LEFT gauge | J6.5 - J6.2 |
| RIGHT gauge | J6.6 - J6.1 |

The PCB joins J6.3 and J6.4 as `Y_SIG`, and joins J6.5 and J6.6 as
`X_SIG`. J6.1 and J6.2 must not be joined.

### Required unpowered resistance check

Disconnect the sensor from the ADC board and measure in resistance mode. If the
traced bridge is correct, exactly these groups should be finite:

| Probe pair | Expected result | Interpretation |
|---|---|---|
| 2-3 | finite | UP gauge |
| 2-5 | finite | LEFT gauge |
| 3-5 | finite, approximately sum of 2-3 and 2-5 | series path via pin 2 |
| 1-4 | finite | DOWN gauge |
| 1-6 | finite | RIGHT gauge |
| 4-6 | finite, approximately sum of 1-4 and 1-6 | series path via pin 1 |

All pairs crossing the `{2,3,5}` and `{1,4,6}` groups should read open before
J6.3+J6.4 and J6.5+J6.6 are externally joined. Do not apply the T440-derived
firmware profile unless this matrix matches. A continuity beeper is insufficient;
record actual resistance values and use a range capable of measuring the gauges.

## ADS1220 measurements

| Logical axis | ADS1220 MUX | Electrical result |
|---|---|---|
| Y | AIN0 - AIN1 | Y_SIG - VCM |
| X | AIN2 - AIN3 | VCM - X_SIG |

The X result has reversed polarity. Apply X inversion in firmware; do not fix
the polarity by shorting or rearranging the differential inputs.

Use external reference 0 (`REFP0`/`REFN0`). Route IDAC1 at 100 uA to REFP0.
The IDAC compliance requirement must be met: REFP0 must remain no higher than
AVDD minus 0.9 V.

## ADS1220IRVAR pin disposition

| U1 pin | Name | Connection |
|---|---|---|
| 1 | CLK | GND for internal oscillator |
| 2 | DGND | GND |
| 3 | AVSS | GND |
| 4 | AIN3/REFN1 | X_SIG |
| 5 | AIN2 | VCM through R9 |
| 6 | REFN0 | REFN0 |
| 7 | REFP0 | REFP0 |
| 8 | AIN1 | VCM through R8 |
| 9 | AIN0/REFP1 | Y_SIG |
| 10 | AVDD | VCC_3V3 |
| 11 | DVDD | VCC_3V3 |
| 12 | DRDY | J1.4 |
| 13 | DOUT/DRDY | R1 to J1.5 |
| 14 | DIN | R2 from J1.6 |
| 15 | SCLK | R3 from J1.3 |
| 16 | CS | GND; valid only for a dedicated SPI bus |
| EP | Thermal pad | Leave open or connect only to AVSS/GND |

The host SPI controller must use mode 1 (`CPOL=0`, `CPHA=1`).

## Relationship to badjeff's working configuration

The reference configuration in
`samukun__ads1220_tpoint_idac.dtsi` converts a four-wire T440 bridge as follows:

| T440 role | ADS1220 connection |
|---|---|
| X output | AIN0 |
| Y output | AIN1 |
| Excitation high | REFP0, driven by IDAC1 |
| Excitation low | REFN0 and AVSS |
| Measurement midpoint | AIN2 through equal 2.4 kohm resistors to REFP0 and REFN0 |

Under the traced LPPS hypothesis, the sensor has six wires because each axis
midpoint is exposed as two terminals. Joining J6.3+J6.4 and J6.5+J6.6 reduces it
to the same four electrical roles: two outputs plus excitation high and low.
R8/R9 create the midpoint used as the negative ADC input. R7/R10 must remain DNP
or the sensor outputs are shorted to that midpoint.

If the resistance matrix above matches, the normal firmware reads:

| Firmware channel | MUX | Axis |
|---|---|---|
| CH0 | AIN3 - AIN2 | X (`X_SIG - VCM`) |
| CH1 | AIN0 - AIN1 | Y (`Y_SIG - VCM`) |
| CH2 | AIN0 - AVSS | Y common-mode monitor only |
| CH3 | AIN3 - AVSS | X common-mode monitor only |

CH0 and CH1 use external reference 0, PGA bypass, gain 4, 330 SPS, and a 100 uA
IDAC on REFP0. The lower bypassed gain is intentional: the connected sensor was
measured near AVSS and therefore does not satisfy the ADS1220 PGA common-mode
requirements at gain 64. Do not fit R7 or R10.

On the first successful 10 uA scan after reconnecting the sensor, MUX12 measured
approximately 123,000 counts with the 2.048 V internal reference. MUX12 is the
ADS1220's divided-by-four reference monitor, so this represents approximately
120 mV across REFP0-REFN0 and an excitation-path resistance near 12 kohm. MUX13
indicated AVDD approximately 3.29 V. A 250 uA IDAC would require about 3.0 V and
violate the IDAC compliance limit; 100 uA is used instead and should produce
about 1.2 V.

## Why the earlier firmware could not validate this circuit

The imported driver placed the external-reference selection into CONFIG2 bits
5:4 instead of bits 7:6. Consequently, `ADC_REF_EXTERNAL0` still measured with
the internal reference. It also set CONFIG1 bit 2 while calling the mode
single-shot; that bit actually selects continuous conversion. Finally, it sent
POWERDOWN before every channel setup and did not support PGA bypass for
AINx-to-AVSS diagnostics. The diagnostic branch corrects these register and
conversion-sequencing errors.

## Diagnostic firmware

`MKB_L_MODULE_LPPS_SCAN` is deliberately separate from the pointer firmware.
It keeps the IDAC at 100 uA and uses the internal reference. Differential MUX0
through MUX7 use gain 4 at 20 SPS; monitor MUX8 through MUX14 use gain 1 at
20 SPS. It emits all 15 ADS1220 MUX results as two lines:

```text
ADSSCAN0,time,mux0,mux1,mux2,mux3,mux4,mux5,mux6,mux7
ADSSCAN1,time,mux8,mux9,mux10,mux11,mux12,mux13,mux14
```

MUX order is the ADS1220 data-sheet order: AIN0-AIN1, AIN0-AIN2,
AIN0-AIN3, AIN1-AIN2, AIN1-AIN3, AIN2-AIN3, AIN1-AIN0,
AIN3-AIN2, AIN0-AVSS, AIN1-AVSS, AIN2-AVSS, AIN3-AVSS,
REFP0-REFN0, AVDD/4-AVSS, and internal short.

Before using the normal 100 uA firmware, run the scan firmware and multiply the
MUX12 voltage result by four to recover REFP0-REFN0. Confirm that this excitation
voltage remains below AVDD minus 0.9 V. Do not tune gain or deadzone until the
IDAC compliance requirement is met.

### Topology discovery mode

`MKB_L_MODULE_LPPS_TOPOLOGY` is a faster variant of the same all-MUX scan. Use it
only after temporarily removing R8 and R9. With R8/R9 fitted, LPPS connector pins
4 and 5 are hard-clamped to VCM through zero-ohm links, so the ADC cannot tell
whether those sensor terminals are true bridge midpoints or part of another
gauge pair. That is why the previous scans showed AIN1 and AIN2 sitting at the
same VCM level regardless of stick motion.

The topology test state should be:

| Item | State |
|---|---|
| R7 | DNP |
| R8 | DNP temporarily |
| R9 | DNP temporarily |
| R10 | DNP |
| R11 | Fit |
| J6.1 | REFN0 |
| J6.2 | REFP0 |
| J6.3 | AIN0 |
| J6.4 | AIN1 |
| J6.5 | AIN2 |
| J6.6 | AIN3 |

In this state, press neutral/up/down/left/right while recording ADSSCAN0/1. The
responsive differential pairs identify the actual half-bridge terminals. Only
after those pairs are known should R8/R9 or any external shorts be reintroduced.
