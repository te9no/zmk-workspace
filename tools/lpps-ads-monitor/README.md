# LPPS ADS Monitor

Web Serial dashboard for the XIAO/ZMK CDC logging port.

```sh
cd /home/owner/zmk-workspace2/zmk-workspace2
python3 -m http.server 8765 --bind 0.0.0.0 --directory tools/lpps-ads-monitor
```

Open `http://localhost:8765` in Chrome or Edge and select the XIAO CDC port.
Close other serial terminals before connecting.

Accepted input formats:

```text
analog_axis_hires_0: ch0:-42 ch1:17 axis0:-40 axis1:15 out0:0 out1:1
ADSCSV,1234,4000000,3990000,-12,34,0,1
ADSCSV4,1234,4000000,3990000,3980000,3970000,-12,34,-56,78,0,1,0,-1
```

`ADSCSV` fields are device uptime, CH0 raw, CH1 raw, CH0 center delta,
CH1 center delta, CH0 output, and CH1 output. The monitor displays both raw
values and plots the center deltas.

`ADSCSV4` extends the same layout to CH0 through CH3. With legacy two-channel
input, CH2 and CH3 remain visible as `--`.
