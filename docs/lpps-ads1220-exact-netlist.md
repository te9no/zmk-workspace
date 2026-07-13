# LPPS + ADS1220IRVAR exact schematic

This document is the electrical source of truth for the LPPS module using the
ADS1220IRVAR (RVA, 16-pin VQFN). It describes the R7/R10 DNP assembly option.

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
| R8 | 0 ohm, AIN1-to-VCM | Fit |
| R9 | 0 ohm, AIN2-to-VCM | Fit |
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

## LPPS internal connections

| Element | LPPS terminals |
|---|---|
| UP gauge | J6.3 - J6.2 |
| DOWN gauge | J6.4 - J6.1 |
| LEFT gauge | J6.5 - J6.2 |
| RIGHT gauge | J6.6 - J6.1 |

The PCB joins J6.3 and J6.4 as `Y_SIG`, and joins J6.5 and J6.6 as
`X_SIG`. J6.1 and J6.2 must not be joined.

## ADS1220 measurements

| Logical axis | ADS1220 MUX | Electrical result |
|---|---|---|
| Y | AIN0 - AIN1 | Y_SIG - VCM |
| X | AIN2 - AIN3 | VCM - X_SIG |

The X result has reversed polarity. Apply X inversion in firmware; do not fix
the polarity by shorting or rearranging the differential inputs.

Use external reference 0 (`REFP0`/`REFN0`). Route IDAC1 at 250 uA to REFP0.
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
